#!/usr/bin/env python3
"""Claude Console helpers for session parsing and stream bridging."""

from __future__ import annotations

import json
import os
import pty
import re
import shutil
import subprocess
import threading
import time
import uuid
from queue import Empty, Queue
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROUTE_LINE_RE = re.compile(r"^\s*\[route:[^\]]+\]\s*$", re.IGNORECASE)
SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;\n\r]+")
COMMON_FILLER_PREFIX_RE = re.compile(
    r"^(?:请你|请先|请|帮我|麻烦你|麻烦|可以|能不能|现在|立刻|直接|继续|先|我想让你|我需要你|需要你|替我|给我|帮忙|帮我把|帮我先|你帮我)\s*",
    re.IGNORECASE,
)
EN_FILLER_PREFIX_RE = re.compile(
    r"^(?:please|could you|can you|help me|i need you to|i want you to|let'?s)\s+",
    re.IGNORECASE,
)
TITLE_TRAILING_NOISE_RE = re.compile(r"(?:一下|一轮|看看|处理下|处理一下|先|吧|哈|呀|呢)$")
TITLE_PUNCT_RE = re.compile(r"[\"'“”‘’`]+")
TOPIC_RULES: List[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(桌面|desktop).{0,12}(截图|截屏|照片|图片|png|jpg|jpeg|webp|heic)", re.IGNORECASE), "桌面文件"),
    (re.compile(r"(删除|清理|移除).{0,12}(截图|截屏|照片|图片|文件)", re.IGNORECASE), "桌面文件"),
    (re.compile(r"(截图|截屏|图像|图片|视觉|vision|ui|界面|ocr|figma)", re.IGNORECASE), "视觉界面"),
    (re.compile(r"(修复|排查|解决|debug|bug|报错|错误|异常|fix)", re.IGNORECASE), "故障修复"),
    (re.compile(r"(审查|核验|review|audit|diff|变更|回归|检查)", re.IGNORECASE), "代码核验"),
    (re.compile(r"(部署|发布|上线|deploy|release|server|gateway|launchagent)", re.IGNORECASE), "部署运维"),
    (re.compile(r"(自动化|workflow|cron|脚本|agent|守护|路由)", re.IGNORECASE), "自动化流程"),
    (re.compile(r"(文档|总结|汇总|写作|report|summary|paper|ppt|slide)", re.IGNORECASE), "文档整理"),
]
FOLDER_NAME_RULES: List[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(gateway|cron|launchagent|workflow|scheduler|feishu)", re.IGNORECASE), "Operations"),
    (re.compile(r"(codex|claude code|claude console)", re.IGNORECASE), "Claude Code"),
]
SESSION_CACHE: Dict[str, Dict[str, Any]] = {}
SESSION_CACHE_LOCK = threading.Lock()
SESSION_LIST_CACHE: Dict[str, Dict[str, Any]] = {}
SESSION_LIST_CACHE_LOCK = threading.Lock()
ACTIVE_RUNS: Dict[str, Dict[str, Any]] = {}
ACTIVE_RUNS_LOCK = threading.Lock()
CLAUDE_STREAM_IDLE_TIMEOUT_SECONDS = int(os.getenv("CLAUDE_STREAM_IDLE_TIMEOUT_SECONDS", "300"))
CLAUDE_STREAM_HARD_TIMEOUT_SECONDS = int(os.getenv("CLAUDE_STREAM_HARD_TIMEOUT_SECONDS", "3600"))
LOCAL_NO_PROXY_VALUE = "127.0.0.1,localhost"
PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
CONTROL_MARKER_RE = re.compile(
    r"<(?:OPENCLAW|CLAUDE)_(?:RUN_STATE|COMPLETION_GATE|SELFCHECK)>\s*(?:COMPLETE|CONTINUE|BLOCKED|PASS|FAIL)\s*</(?:OPENCLAW|CLAUDE)_(?:RUN_STATE|COMPLETION_GATE|SELFCHECK)>",
    re.IGNORECASE,
)
ANSI_ESCAPE_RE = re.compile(r"\x1b(?:[@-Z\-_]|\[[0-?]*[ -/]*[@-~]|\][^\a]*(?:\a|\x1b\\))", re.IGNORECASE)
DISPLAY_MODEL_ALIASES = {
    "claude-opus-4-6": "claude-opus-4-6-thinking",
}
DEFAULT_PERMISSION_MODE = (os.getenv("CLAUDE_WEB_PERMISSION_MODE", "bypassPermissions") or "bypassPermissions").strip()


def normalize_display_model(model_name: str) -> str:
    normalized = str(model_name or "").strip()
    return DISPLAY_MODEL_ALIASES.get(normalized, normalized)


def project_slug_from_path(workspace_root: str) -> str:
    normalized = os.path.abspath(os.path.expanduser(workspace_root))
    slug = normalized.replace("\\", "/").replace("/", "-")
    return slug if slug.startswith("-") else f"-{slug}"


def project_sessions_dir(claude_home: str, workspace_root: str) -> str:
    return os.path.join(os.path.expanduser(claude_home), "projects", project_slug_from_path(workspace_root))


def ensure_meta_store(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("sessions"), dict):
                return data
        except Exception:
            pass
    return {"sessions": {}}


def save_meta_store(path: str, data: Dict[str, Any]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_folder_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip()[:32]


def list_folder_registry(meta_path: str, sessions: Optional[Iterable[Dict[str, Any]]] = None) -> List[str]:
    store = ensure_meta_store(meta_path)
    ordered: List[str] = []
    seen: set[str] = set()

    raw_folders = store.get("folders") or []
    if isinstance(raw_folders, list):
        for item in raw_folders:
            folder = normalize_folder_name(str(item or ""))
            if folder and folder not in seen:
                ordered.append(folder)
                seen.add(folder)

    for session in sessions or []:
        if not isinstance(session, dict):
            continue
        folder = normalize_folder_name(str(session.get("folder") or ""))
        if folder and folder not in seen:
            ordered.append(folder)
            seen.add(folder)

    return ordered


def create_folder(meta_path: str, folder_name: str) -> List[str]:
    normalized = normalize_folder_name(folder_name)
    if not normalized:
        raise ValueError("missing folder name")
    store = ensure_meta_store(meta_path)
    folders = store.setdefault("folders", [])
    if not isinstance(folders, list):
        folders = []
        store["folders"] = folders
    if normalized not in folders:
        folders.append(normalized)
    save_meta_store(meta_path, store)
    return list_folder_registry(meta_path)


def rename_folder(
    meta_path: str,
    old_name: str,
    new_name: str,
    *,
    session_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    old_normalized = normalize_folder_name(old_name)
    new_normalized = normalize_folder_name(new_name)
    if not old_normalized or not new_normalized:
        raise ValueError("missing folder name")

    store = ensure_meta_store(meta_path)
    folders = store.setdefault("folders", [])
    if not isinstance(folders, list):
        folders = []
        store["folders"] = folders

    updated_sessions = 0
    if old_normalized in folders:
        folders = [new_normalized if item == old_normalized else item for item in folders]
    elif new_normalized not in folders:
        folders.append(new_normalized)
    store["folders"] = list(dict.fromkeys(normalize_folder_name(item) for item in folders if normalize_folder_name(item)))

    target_ids = {Path(str(item or "")).stem.strip() for item in (session_ids or []) if Path(str(item or "")).stem.strip()}
    sessions = store.setdefault("sessions", {})
    if isinstance(sessions, dict):
        for session_id, meta in sessions.items():
            if not isinstance(meta, dict):
                continue
            current_folder = normalize_folder_name(str(meta.get("folder") or ""))
            if current_folder == old_normalized or session_id in target_ids:
                meta["folder"] = new_normalized
                updated_sessions += 1
        for session_id in target_ids:
            meta = sessions.setdefault(session_id, {})
            if isinstance(meta, dict):
                meta["folder"] = new_normalized

    save_meta_store(meta_path, store)
    return {
        "oldName": old_normalized,
        "newName": new_normalized,
        "updatedSessions": updated_sessions,
        "folders": list_folder_registry(meta_path),
    }


def update_session_meta(
    meta_path: str,
    session_id: str,
    *,
    title: Optional[str] = None,
    folder: Optional[str] = None,
    archived: Optional[bool] = None,
    pinned: Optional[bool] = None,
) -> Dict[str, Any]:
    store = ensure_meta_store(meta_path)
    sessions = store.setdefault("sessions", {})
    current = sessions.setdefault(session_id, {})
    if title is not None:
        current["title"] = title.strip()
    if folder is not None:
        current["folder"] = folder.strip()
    if archived is not None:
        current["archived"] = bool(archived)
    if pinned is not None:
        current["pinned"] = bool(pinned)
    current["updatedAt"] = datetime.now().isoformat()
    save_meta_store(meta_path, store)
    return current


def strip_route_lines(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned_lines = []
    for raw in text.replace("\r", "").split("\n"):
        if ROUTE_LINE_RE.match(raw or ""):
            continue
        cleaned_lines.append(raw)
    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned


def clip_text(text: str, limit: int = 88) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _clean_title_seed(text: str) -> str:
    cleaned = strip_route_lines(text)
    cleaned = TITLE_PUNCT_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    first = SENTENCE_SPLIT_RE.split(cleaned)[0].strip()
    seed = first
    for _ in range(3):
        next_seed = COMMON_FILLER_PREFIX_RE.sub("", seed).strip()
        next_seed = EN_FILLER_PREFIX_RE.sub("", next_seed).strip()
        if next_seed == seed:
            break
        seed = next_seed
    seed = seed.lstrip("，,：:、.- ").strip()
    seed = TITLE_TRAILING_NOISE_RE.sub("", seed).strip()
    return seed or cleaned


def derive_session_topic(text: str) -> str:
    seed = _clean_title_seed(text)
    haystack = seed or text or ""
    for pattern, label in TOPIC_RULES:
        if pattern.search(haystack):
            return label
    return "通用对话"


def derive_session_folder(title: str, topic: str = "", special_role: str = "") -> str:
    role = str(special_role or "").strip().lower()
    if "openclaw" in role:
        return "Operations"
    haystack = "\n".join(part for part in [title, topic, special_role] if str(part or "").strip())
    for pattern, label in FOLDER_NAME_RULES:
        if pattern.search(haystack):
            return label
    normalized_topic = str(topic or "").strip()
    if normalized_topic and normalized_topic != "通用对话":
        return normalized_topic
    seed = _clean_title_seed(title)
    if seed and not re.search(r"[\u4e00-\u9fff]", seed):
        english_head = re.split(r"[\s/_-]+", seed)[0].strip()
        if english_head:
            return clip_text(english_head, 18)
    return "未归类"


def derive_session_title(text: str) -> str:
    seed = _clean_title_seed(text)
    if not seed:
        return "新对话"

    special_cases: List[tuple[re.Pattern[str], str]] = [
        (re.compile(r"(删除|清理|移除).{0,12}(桌面|desktop).{0,12}(截图|截屏|照片|图片)", re.IGNORECASE), "删除桌面截屏照片"),
        (re.compile(r"(修复|排查|解决).{0,20}(报错|错误|问题|bug)", re.IGNORECASE), "修复关键报错"),
        (re.compile(r"(审查|核验|review|audit).{0,20}(代码|diff|变更)", re.IGNORECASE), "代码变更核验"),
        (re.compile(r"(部署|发布|上线|deploy|release)", re.IGNORECASE), "部署发布流程"),
        (re.compile(r"(截图|截屏|图像|视觉|vision|界面|ui|ocr)", re.IGNORECASE), "界面截图分析"),
        (re.compile(r"(自动化|workflow|cron|agent|守护)", re.IGNORECASE), "自动化流程调整"),
        (re.compile(r"^(create|new).{0,12}(file|文件)", re.IGNORECASE), "文件创建请求"),
        (re.compile(r"^(update|edit|modify).{0,12}(/|file|文件)", re.IGNORECASE), "文件更新请求"),
    ]
    for pattern, title in special_cases:
        if pattern.search(seed):
            return title

    if re.search(r"[\u4e00-\u9fff]", seed):
        compact = re.sub(r"\s+", "", seed)
        compact = compact.strip("，。！？；、:： ")
        return clip_text(compact or seed, 16)

    words = [part for part in re.split(r"\s+", seed) if part]
    if not words:
        return "新对话"
    english_title = " ".join(words[:4]).strip()
    return clip_text(english_title[:1].upper() + english_title[1:], 40)


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def as_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    parsed = parse_iso_datetime(value)
    if parsed is not None:
        return parsed.isoformat()
    return datetime.now().isoformat()


def summarize_block_text(block: Dict[str, Any]) -> str:
    block_type = block.get("type")
    if block_type == "text":
        return CONTROL_MARKER_RE.sub("", str(block.get("text") or "")).strip()
    if block_type == "thinking":
        return str(block.get("text") or "")
    if block_type == "tool_use":
        name = str(block.get("name") or "工具")
        return f"[工具:{name}]"
    if block_type == "tool_result":
        return CONTROL_MARKER_RE.sub("", str(block.get("text") or "")).strip()
    return CONTROL_MARKER_RE.sub("", str(block.get("text") or "")).strip()


def parse_content_blocks(content: Any) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    if isinstance(content, str):
        if content.strip():
            blocks.append({"type": "text", "text": content})
        return blocks
    if not isinstance(content, list):
        return blocks

    for item in content:
        if isinstance(item, str):
            if item.strip():
                blocks.append({"type": "text", "text": item})
            continue
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "unknown")
        if kind == "text":
            text = str(item.get("text") or "")
            if text:
                blocks.append({"type": "text", "text": text})
            continue
        if kind == "thinking":
            thinking = str(item.get("thinking") or "")
            blocks.append({"type": "thinking", "text": thinking, "signature": str(item.get("signature") or "")})
            continue
        if kind == "tool_use":
            blocks.append(
                {
                    "type": "tool_use",
                    "id": str(item.get("id") or ""),
                    "name": str(item.get("name") or "工具"),
                    "input": item.get("input") or {},
                }
            )
            continue
        if kind == "tool_result":
            tool_text = item.get("content")
            if isinstance(tool_text, list):
                tool_text = "\n".join(str(part) for part in tool_text)
            blocks.append(
                {
                    "type": "tool_result",
                    "text": str(tool_text or ""),
                    "isError": bool(item.get("is_error")),
                    "toolUseId": str(item.get("tool_use_id") or ""),
                }
            )
            continue
        blocks.append({"type": kind, "text": json.dumps(item, ensure_ascii=False)})

    return blocks


def merge_blocks(existing: List[Dict[str, Any]], incoming: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = list(existing)
    for block in incoming:
        if not block:
            continue
        if merged and block == merged[-1]:
            continue
        merged.append(block)
    return merged


def display_text_from_blocks(blocks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type == "thinking":
            continue
        text = summarize_block_text(block).strip()
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def thinking_text_from_blocks(blocks: List[Dict[str, Any]]) -> str:
    parts = [str(block.get("text") or "").strip() for block in blocks if block.get("type") == "thinking" and str(block.get("text") or "").strip()]
    return "\n".join(parts).strip()


def normalize_user_content(message: Dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return strip_route_lines(content)
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    parts.append(item.strip())
                continue
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type") or "")
            if kind == "text" and str(item.get("text") or "").strip():
                parts.append(str(item.get("text") or "").strip())
            elif kind == "tool_result":
                raw_content = item.get("content")
                if isinstance(raw_content, str):
                    parts.append(raw_content.strip())
        return strip_route_lines("\n".join(parts))
    return ""


def is_tool_result_user(obj: Dict[str, Any]) -> bool:
    if obj.get("type") != "user":
        return False
    if obj.get("tool_use_result") is not None:
        return True
    message = obj.get("message") or {}
    content = message.get("content")
    if not isinstance(content, list) or not content:
        return False
    for item in content:
        if isinstance(item, dict) and str(item.get("type") or "") == "tool_result":
            return True
    return False


def _session_cache_key(path: str) -> str:
    return os.path.abspath(path)


def _file_state_signature(path: str) -> tuple[int, int]:
    try:
        st = os.stat(path)
        return (int(st.st_mtime_ns), int(st.st_size))
    except OSError:
        return (0, 0)


def _candidate_session_paths(
    sessions_dir: Path,
    meta_sessions: Dict[str, Any],
    *,
    include_archived: bool,
    limit: int,
) -> List[Path]:
    sorted_paths = sorted(
        sessions_dir.glob("*.jsonl"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not sorted_paths:
        return []

    recent_cap = max(limit * 3, 240)
    if include_archived:
        recent_cap = max(recent_cap, 320)

    chosen: List[Path] = []
    chosen_lookup: set[str] = set()
    for path in sorted_paths:
        if _is_agent_setting_shell(path):
            continue
        chosen.append(path)
        chosen_lookup.add(path.name)
        if len(chosen) >= recent_cap:
            break
    priority_ids: set[str] = set()

    for session_id, meta in (meta_sessions or {}).items():
        if not isinstance(meta, dict):
            continue
        if bool(meta.get("pinned")) or bool(meta.get("fixed")) or (include_archived and bool(meta.get("archived"))):
            safe_id = Path(str(session_id or "")).stem.strip()
            if safe_id:
                priority_ids.add(safe_id)

    for session_id in sorted(priority_ids):
        candidate = sessions_dir / f"{session_id}.jsonl"
        if candidate.exists() and candidate.name not in chosen_lookup:
            chosen.append(candidate)
            chosen_lookup.add(candidate.name)

    return chosen


def _is_agent_setting_shell(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as f:
            saw_record = False
            saw_renderable_content = False
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                saw_record = True
                try:
                    obj = json.loads(line)
                except Exception:
                    return False
                kind = str(obj.get("type") or "").strip()
                if kind == "agent-setting":
                    continue
                if kind == "assistant":
                    saw_renderable_content = True
                    break
                if kind == "user":
                    if is_tool_result_user(obj):
                        saw_renderable_content = True
                        break
                    if normalize_user_content((obj.get("message") or {})).strip():
                        saw_renderable_content = True
                        break
                    continue
                return False
            return saw_record and not saw_renderable_content
    except Exception:
        return False


def parse_session_file(path: str) -> Dict[str, Any]:
    abs_path = _session_cache_key(path)
    st = os.stat(abs_path)
    cache_key = abs_path
    with SESSION_CACHE_LOCK:
        cached = SESSION_CACHE.get(cache_key)
        if cached and cached.get("mtime") == st.st_mtime and cached.get("size") == st.st_size:
            return cached["data"]

    session_id = Path(abs_path).stem
    summary: Dict[str, Any] = {
        "id": session_id,
        "sessionId": session_id,
        "title": "",
        "topic": "",
        "folder": "",
        "preview": "",
        "createdAt": datetime.fromtimestamp(st.st_ctime).isoformat(),
        "updatedAt": datetime.fromtimestamp(st.st_mtime).isoformat(),
        "path": abs_path,
        "messageCount": 0,
        "userMessageCount": 0,
        "assistantMessageCount": 0,
        "toolMessageCount": 0,
        "model": "",
        "shellOnly": False,
    }
    messages: List[Dict[str, Any]] = []
    assistant_by_key: Dict[str, Dict[str, Any]] = {}

    with open(abs_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            kind = str(obj.get("type") or "")
            timestamp = as_iso(obj.get("timestamp"))
            if parse_iso_datetime(timestamp):
                summary["updatedAt"] = timestamp

            if kind == "user" and not is_tool_result_user(obj):
                message = obj.get("message") or {}
                text = normalize_user_content(message)
                entry = {
                    "id": str(obj.get("uuid") or uuid.uuid4()),
                    "role": "user",
                    "timestamp": timestamp,
                    "displayText": text,
                    "blocks": [{"type": "text", "text": text}] if text else [],
                    "model": "",
                }
                messages.append(entry)
                summary["messageCount"] += 1
                summary["userMessageCount"] += 1
                if not summary["title"] and text:
                    summary["title"] = derive_session_title(text)
                if not summary["topic"] and text:
                    summary["topic"] = derive_session_topic(text)
                if text:
                    summary["preview"] = clip_text(text, 84)
                continue

            if kind == "user" and is_tool_result_user(obj):
                message = obj.get("message") or {}
                blocks = parse_content_blocks(message.get("content"))
                tool_payload = obj.get("tool_use_result")
                tool_text = ""
                if isinstance(tool_payload, dict):
                    if tool_payload.get("type") == "text":
                        file_meta = tool_payload.get("file") or {}
                        tool_text = str(file_meta.get("content") or "")
                    elif tool_payload.get("type") == "update":
                        tool_text = str(tool_payload.get("content") or "")
                if not blocks and tool_text:
                    blocks = [{"type": "tool_result", "text": tool_text, "isError": False, "toolUseId": ""}]
                entry = {
                    "id": str(obj.get("uuid") or uuid.uuid4()),
                    "role": "tool",
                    "timestamp": timestamp,
                    "displayText": display_text_from_blocks(blocks),
                    "blocks": blocks,
                    "model": "",
                }
                messages.append(entry)
                summary["messageCount"] += 1
                summary["toolMessageCount"] += 1
                if entry["displayText"]:
                    summary["preview"] = clip_text(entry["displayText"], 84)
                continue

            if kind != "assistant":
                continue

            message = obj.get("message") or {}
            assistant_id = str(message.get("id") or obj.get("uuid") or uuid.uuid4())
            blocks = parse_content_blocks(message.get("content"))
            entry = assistant_by_key.get(assistant_id)
            if entry is None:
                entry = {
                    "id": assistant_id,
                    "role": "assistant",
                    "timestamp": timestamp,
                    "displayText": "",
                    "thinkingText": "",
                    "blocks": [],
                    "model": normalize_display_model(str(message.get("model") or "")),
                }
                assistant_by_key[assistant_id] = entry
                messages.append(entry)
                summary["messageCount"] += 1
                summary["assistantMessageCount"] += 1
            entry["blocks"] = merge_blocks(entry["blocks"], blocks)
            entry["displayText"] = display_text_from_blocks(entry["blocks"])
            entry["thinkingText"] = thinking_text_from_blocks(entry["blocks"])
            if message.get("model"):
                entry["model"] = normalize_display_model(str(message.get("model")))
                summary["model"] = entry["model"]
            if entry["displayText"]:
                summary["preview"] = clip_text(entry["displayText"], 84)

    if not summary["title"]:
        summary["title"] = "新对话"
    if not summary["topic"]:
        summary["topic"] = derive_session_topic(summary["title"])
    if not summary["folder"]:
        summary["folder"] = derive_session_folder(summary["title"], summary["topic"])
    summary["shellOnly"] = summary["messageCount"] <= 0 and _is_agent_setting_shell(Path(abs_path))

    parsed = {"summary": summary, "messages": messages}
    with SESSION_CACHE_LOCK:
        SESSION_CACHE[cache_key] = {"mtime": st.st_mtime, "size": st.st_size, "data": parsed}
    return parsed


def list_sessions(project_dir: str, meta_path: str, include_archived: bool = False, limit: int = 120) -> List[Dict[str, Any]]:
    sessions_dir = Path(project_dir)
    if not sessions_dir.exists():
        return []
    meta_store = ensure_meta_store(meta_path)
    meta_sessions = meta_store.get("sessions") or {}
    candidate_paths = _candidate_session_paths(
        sessions_dir,
        meta_sessions if isinstance(meta_sessions, dict) else {},
        include_archived=include_archived,
        limit=limit,
    )
    cache_key = json.dumps(
        {
            "projectDir": os.path.realpath(str(sessions_dir)),
            "metaPath": os.path.realpath(str(meta_path)),
            "includeArchived": bool(include_archived),
            "limit": int(limit),
            "metaState": _file_state_signature(meta_path),
            "candidates": [
                (path.name, *(_file_state_signature(str(path))))
                for path in candidate_paths
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    with SESSION_LIST_CACHE_LOCK:
        cached = SESSION_LIST_CACHE.get(cache_key)
        if isinstance(cached, dict) and isinstance(cached.get("items"), list):
            return [dict(item) for item in cached["items"]]

    session_items: List[Dict[str, Any]] = []

    for path in candidate_paths:
        parsed = parse_session_file(str(path))
        summary = dict(parsed["summary"])
        if bool(summary.get("shellOnly")) or int(summary.get("messageCount") or 0) <= 0:
            continue
        meta = meta_sessions.get(summary["sessionId"], {}) if isinstance(meta_sessions, dict) else {}
        title_override = str(meta.get("title") or "").strip()
        topic_override = str(meta.get("topic") or "").strip()
        folder_override = str(meta.get("folder") or "").strip()
        if title_override:
            summary["title"] = title_override
            summary["topic"] = topic_override or derive_session_topic(title_override)
        elif topic_override:
            summary["topic"] = topic_override
        summary["folder"] = folder_override or derive_session_folder(
            str(summary.get("title") or ""),
            str(summary.get("topic") or ""),
            str(meta.get("specialRole") or ""),
        )
        summary["archived"] = bool(meta.get("archived"))
        summary["pinned"] = bool(meta.get("pinned"))
        summary["fixed"] = bool(meta.get("fixed"))
        summary["specialRole"] = str(meta.get("specialRole") or "")
        if summary["archived"] and not include_archived:
            continue
        session_items.append(summary)

    session_items.sort(
        key=lambda item: (
            1 if item.get("pinned") else 0,
            str(item.get("updatedAt") or ""),
        ),
        reverse=True,
    )
    if limit > 0:
        session_items = session_items[:limit]
    with SESSION_LIST_CACHE_LOCK:
        SESSION_LIST_CACHE.clear()
        SESSION_LIST_CACHE[cache_key] = {
            "items": [dict(item) for item in session_items],
            "createdAt": time.time(),
        }
    return session_items


def get_session_detail(project_dir: str, meta_path: str, session_id: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(project_dir, f"{session_id}.jsonl")
    if not os.path.exists(path):
        return None
    parsed = parse_session_file(path)
    summary = dict(parsed["summary"])
    meta_store = ensure_meta_store(meta_path)
    meta = (meta_store.get("sessions") or {}).get(session_id, {})
    title_override = str(meta.get("title") or "").strip()
    topic_override = str(meta.get("topic") or "").strip()
    folder_override = str(meta.get("folder") or "").strip()
    if title_override:
        summary["title"] = title_override
        summary["topic"] = topic_override or derive_session_topic(title_override)
    elif topic_override:
        summary["topic"] = topic_override
    summary["folder"] = folder_override or derive_session_folder(
        str(summary.get("title") or ""),
        str(summary.get("topic") or ""),
        str(meta.get("specialRole") or ""),
    )
    summary["archived"] = bool(meta.get("archived"))
    summary["pinned"] = bool(meta.get("pinned"))
    summary["fixed"] = bool(meta.get("fixed"))
    summary["specialRole"] = str(meta.get("specialRole") or "")
    return {"summary": summary, "messages": parsed["messages"]}


def delete_session(
    project_dir: str,
    meta_path: str,
    session_id: str,
    *,
    trash_root: str,
    protected_session_ids: Optional[set[str]] = None,
) -> Dict[str, Any]:
    safe_session_id = Path(str(session_id or "")).stem.strip()
    if not safe_session_id:
        raise ValueError("missing session id")

    protected_lookup = {str(item).strip() for item in (protected_session_ids or set()) if str(item).strip()}
    if safe_session_id in protected_lookup:
        raise PermissionError("protected session")

    source_path = Path(project_dir) / f"{safe_session_id}.jsonl"
    if not source_path.exists():
        raise FileNotFoundError(safe_session_id)

    target_root = Path(trash_root)
    target_root.mkdir(parents=True, exist_ok=True)
    target_path = target_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_session_id}.jsonl"
    shutil.move(str(source_path), str(target_path))

    store = ensure_meta_store(meta_path)
    sessions = store.setdefault("sessions", {})
    if isinstance(sessions, dict):
        sessions.pop(safe_session_id, None)
    special_sessions = store.get("specialSessions")
    if isinstance(special_sessions, dict):
        for key, value in list(special_sessions.items()):
            if str(value or "").strip() == safe_session_id:
                special_sessions.pop(key, None)
    save_meta_store(meta_path, store)

    cache_key = _session_cache_key(str(source_path))
    with SESSION_CACHE_LOCK:
        SESSION_CACHE.pop(cache_key, None)
    with SESSION_LIST_CACHE_LOCK:
        SESSION_LIST_CACHE.clear()

    return {
        "ok": True,
        "sessionId": safe_session_id,
        "movedTo": str(target_path),
    }


def cleanup_empty_sessions(
    project_dir: str,
    meta_path: str,
    *,
    trash_root: str = "",
    limit: int = 120,
) -> Dict[str, Any]:
    sessions_dir = Path(project_dir)
    if not sessions_dir.exists():
        return {"ok": True, "removed": 0, "items": []}

    removed: List[Dict[str, Any]] = []
    candidates = sorted(
        sessions_dir.glob("*.jsonl"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        if limit > 0 and len(removed) >= limit:
            break
        try:
            parsed = parse_session_file(str(path))
        except Exception:
            continue
        summary = parsed.get("summary") or {}
        if int(summary.get("messageCount") or 0) > 0 or not bool(summary.get("shellOnly")):
            continue
        try:
            deleted = delete_session(
                project_dir,
                meta_path,
                str(summary.get("sessionId") or path.stem),
                trash_root=trash_root,
            )
        except Exception:
            continue
        removed.append(
            {
                "sessionId": str(deleted.get("sessionId") or path.stem),
                "movedTo": str(deleted.get("movedTo") or ""),
            }
        )

    return {"ok": True, "removed": len(removed), "items": removed}


def register_run(run_id: str, process: subprocess.Popen, requested_session_id: Optional[str], prompt: str) -> None:
    with ACTIVE_RUNS_LOCK:
        ACTIVE_RUNS[run_id] = {
            "runId": run_id,
            "process": process,
            "requestedSessionId": requested_session_id,
            "sessionId": requested_session_id,
            "prompt": prompt,
            "startedAt": datetime.now().isoformat(),
            "stopRequested": False,
        }


def attach_run_session(run_id: str, session_id: str) -> None:
    with ACTIVE_RUNS_LOCK:
        item = ACTIVE_RUNS.get(run_id)
        if item is not None:
            item["sessionId"] = session_id


def finish_run(run_id: str) -> Dict[str, Any]:
    with ACTIVE_RUNS_LOCK:
        return ACTIVE_RUNS.pop(run_id, {})


def stop_run(run_id: str) -> Dict[str, Any]:
    with ACTIVE_RUNS_LOCK:
        item = ACTIVE_RUNS.get(run_id)
        if item is None:
            return {"ok": False, "msg": "run not found"}
        item["stopRequested"] = True
        process = item.get("process")
    try:
        if process and process.poll() is None:
            process.terminate()
        return {"ok": True, "runId": run_id}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def list_active_runs() -> List[Dict[str, Any]]:
    with ACTIVE_RUNS_LOCK:
        items = []
        for run_id, item in ACTIVE_RUNS.items():
            items.append(
                {
                    "runId": run_id,
                    "sessionId": item.get("sessionId"),
                    "requestedSessionId": item.get("requestedSessionId"),
                    "startedAt": item.get("startedAt"),
                    "stopRequested": bool(item.get("stopRequested")),
                }
            )
        return items


def _normalize_delta_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    event_type = str(event.get("type") or "")
    if event_type == "content_block_start":
        block = event.get("content_block") or {}
        block_type = str(block.get("type") or "")
        if block_type == "text":
            return {"type": "block_start", "channel": "text"}
        if block_type == "thinking":
            return {"type": "block_start", "channel": "thinking"}
        if block_type == "tool_use":
            return {
                "type": "tool_start",
                "toolId": str(block.get("id") or ""),
                "name": str(block.get("name") or "工具"),
            }
        return None
    if event_type == "content_block_delta":
        delta = event.get("delta") or {}
        delta_type = str(delta.get("type") or "")
        if delta_type == "text_delta":
            return {"type": "delta", "channel": "text", "text": str(delta.get("text") or "")}
        if delta_type == "thinking_delta":
            return {"type": "delta", "channel": "thinking", "text": str(delta.get("thinking") or "")}
        if delta_type == "input_json_delta":
            return {"type": "tool_delta", "text": str(delta.get("partial_json") or "")}
        if delta_type == "signature_delta":
            return None
    if event_type == "message_delta":
        return {
            "type": "message_delta",
            "stopReason": (event.get("delta") or {}).get("stop_reason"),
        }
    return None


def _strip_terminal_control_text(text: str) -> str:
    cleaned = ANSI_ESCAPE_RE.sub("", str(text or ""))
    cleaned = cleaned.replace("\r", "")
    cleaned = cleaned.replace("\x08", "")
    cleaned = cleaned.replace("\x00", "")
    return cleaned


def _clean_subprocess_env() -> Dict[str, str]:
    clean_env = os.environ.copy()
    clean_env["NO_PROXY"] = LOCAL_NO_PROXY_VALUE
    clean_env["no_proxy"] = LOCAL_NO_PROXY_VALUE
    clean_env.setdefault("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", "1")
    for key in PROXY_ENV_KEYS:
        clean_env.pop(key, None)
    return clean_env


def _spawn_pty_process(cmd: List[str], cwd: str) -> tuple[subprocess.Popen, int]:
    master_fd, slave_fd = pty.openpty()
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=_clean_subprocess_env(),
            stdin=subprocess.DEVNULL,
            stdout=slave_fd,
            stderr=slave_fd,
            text=False,
            bufsize=0,
            close_fds=True,
        )
    finally:
        try:
            os.close(slave_fd)
        except OSError:
            pass
    return process, master_fd


def _spawn_pipe_process(cmd: List[str], cwd: str) -> subprocess.Popen:
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=_clean_subprocess_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=False,
        bufsize=0,
        close_fds=True,
    )
    if process.stdout is None:
        raise RuntimeError("stdout pipe unavailable")
    return process


def _stream_pty_lines(master_fd: int, out_queue: Queue) -> None:
    buffer = ""
    try:
        while True:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                cleaned = _strip_terminal_control_text(line)
                if cleaned or line:
                    out_queue.put(("pty", cleaned + "\n"))
    finally:
        cleaned_buffer = _strip_terminal_control_text(buffer)
        if cleaned_buffer.strip():
            out_queue.put(("pty", cleaned_buffer))
        try:
            os.close(master_fd)
        except OSError:
            pass
        out_queue.put(("pty", None))


def _stream_pipe_lines(stream, out_queue: Queue) -> None:
    buffer = ""
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                cleaned = _strip_terminal_control_text(line)
                if cleaned or line:
                    out_queue.put(("pipe", cleaned + "\n"))
    finally:
        cleaned_buffer = _strip_terminal_control_text(buffer)
        if cleaned_buffer.strip():
            out_queue.put(("pipe", cleaned_buffer))
        try:
            stream.close()
        except Exception:
            pass
        out_queue.put(("pipe", None))


def _spawn_stream_process(cmd: List[str], cwd: str) -> tuple[subprocess.Popen, Queue, str, str]:
    stream_queue: Queue = Queue()
    try:
        process, master_fd = _spawn_pty_process(cmd, cwd)
        threading.Thread(target=_stream_pty_lines, args=(master_fd, stream_queue), daemon=True).start()
        return process, stream_queue, "pty", ""
    except OSError as exc:
        process = _spawn_pipe_process(cmd, cwd)
        threading.Thread(target=_stream_pipe_lines, args=(process.stdout, stream_queue), daemon=True).start()
        return process, stream_queue, "pipe", str(exc)


def run_claude_capture(
    claude_bin: str,
    workspace_root: str,
    prompt: str,
    *,
    session_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    add_dirs: Optional[List[str]] = None,
    timeout_seconds: int = 180,
) -> Dict[str, Any]:
    prepared_prompt = str(prompt or "").strip()
    if not prepared_prompt:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": "missing prompt"}

    cmd: List[str] = [claude_bin, "-p"]
    if permission_mode == "bypassPermissions":
        cmd.append("--dangerously-skip-permissions")
    cmd.extend(["--permission-mode", permission_mode])
    if agent_name:
        cmd.extend(["--agent", agent_name])
    for add_dir in add_dirs or []:
        candidate = os.path.realpath(os.path.expanduser(str(add_dir or "").strip()))
        workspace_real = os.path.realpath(os.path.expanduser(workspace_root))
        if not candidate or candidate == workspace_real or not os.path.exists(candidate):
            continue
        cmd.append(f"--add-dir={candidate}")
    if session_id:
        cmd.extend(["--resume", session_id])
    cmd.append(prepared_prompt)

    process, stream_queue, transport, transport_error = _spawn_stream_process(cmd, workspace_root)
    collected: list[str] = []
    timed_out = False
    started = time.monotonic()

    try:
        while True:
            if time.monotonic() - started > timeout_seconds:
                timed_out = True
                if process.poll() is None:
                    process.terminate()
                break
            if process.poll() is not None and stream_queue.empty():
                break
            try:
                _, raw = stream_queue.get(timeout=1.0)
            except Empty:
                continue
            if raw is None:
                if process.poll() is not None:
                    break
                continue
            collected.append(raw)

        try:
            return_code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                process.kill()
            return_code = process.wait(timeout=5)

        stdout_text = _strip_terminal_control_text("".join(collected)).strip()
        execution_error = stdout_text.lower() in {"execution error", "internal server error"}
        return {
            "ok": return_code == 0 and not timed_out and not execution_error,
            "returncode": return_code,
            "stdout": stdout_text,
            "stderr": stdout_text if execution_error else "",
            "timedOut": timed_out,
            "transport": transport,
            "transportError": transport_error,
        }
    finally:
        if process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass


def stream_claude_session(
    claude_bin: str,
    workspace_root: str,
    prompt: str,
    *,
    session_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    add_dirs: Optional[List[str]] = None,
    timeout_seconds: int = 1800,
) -> Iterable[Dict[str, Any]]:
    prepared_prompt = str(prompt or "").strip()
    if not prepared_prompt:
        raise ValueError("Claude 会话缺少输入内容，已阻止空 prompt 落入 --print 模式")
    run_id = str(uuid.uuid4())
    cmd: List[str] = [
        claude_bin,
        "-p",
        "--verbose",
        "--output-format",
        "stream-json",
        "--include-partial-messages",
    ]
    if permission_mode == "bypassPermissions":
        cmd.append("--dangerously-skip-permissions")
    cmd.extend(["--permission-mode", permission_mode])
    if agent_name:
        cmd.extend(["--agent", agent_name])
    for add_dir in add_dirs or []:
        candidate = os.path.realpath(os.path.expanduser(str(add_dir or "").strip()))
        workspace_real = os.path.realpath(os.path.expanduser(workspace_root))
        if not candidate or candidate == workspace_real or not os.path.exists(candidate):
            continue
        cmd.append(f"--add-dir={candidate}")
    if session_id:
        cmd.extend(["--resume", session_id])
    cmd.append(prepared_prompt)

    process, stream_queue, transport, transport_error = _spawn_stream_process(cmd, workspace_root)
    register_run(run_id, process, session_id, prepared_prompt)
    actual_session_id = session_id
    root_session_id = str(session_id or "").strip()
    saw_result = False
    terminal_event_emitted = False
    stderr_lines: list[str] = []
    stream_closed = False
    last_activity_monotonic = time.monotonic()
    started_monotonic = last_activity_monotonic
    yield {
        "type": "run_start",
        "runId": run_id,
        "requestedSessionId": session_id,
        "transport": transport,
    }
    if transport != "pty":
        yield {
            "type": "system_notice",
            "runId": run_id,
            "sessionId": actual_session_id,
            "message": "系统 PTY 资源不足，已自动切换为兼容执行模式继续任务。",
            "transport": transport,
            "detail": transport_error,
        }

    try:
        while True:
            if time.monotonic() - started_monotonic > min(timeout_seconds, CLAUDE_STREAM_HARD_TIMEOUT_SECONDS):
                if process.poll() is None:
                    process.terminate()
                terminal_event_emitted = True
                yield {
                    "type": "done",
                    "runId": run_id,
                    "sessionId": actual_session_id,
                    "result": "",
                    "isError": True,
                    "stopReason": "hard_timeout",
                    "stderr": "\n".join(stderr_lines).strip(),
                    "durationMs": None,
                }
                break

            if time.monotonic() - last_activity_monotonic > CLAUDE_STREAM_IDLE_TIMEOUT_SECONDS:
                if process.poll() is None:
                    process.terminate()
                terminal_event_emitted = True
                yield {
                    "type": "done",
                    "runId": run_id,
                    "sessionId": actual_session_id,
                    "result": "",
                    "isError": True,
                    "stopReason": "idle_timeout",
                    "stderr": "\n".join(stderr_lines).strip(),
                    "durationMs": None,
                }
                break

            if stream_closed and process.poll() is not None:
                break

            try:
                _, raw = stream_queue.get(timeout=1.0)
            except Empty:
                continue

            if raw is None:
                stream_closed = True
                continue

            last_activity_monotonic = time.monotonic()
            line = _strip_terminal_control_text(str(raw or "")).strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                stderr_lines.append(line)
                if len(stderr_lines) > 400:
                    stderr_lines = stderr_lines[-400:]
                yield {"type": "debug", "runId": run_id, "line": line[:400]}
                continue

            record_type = str(payload.get("type") or "")
            if record_type == "system" and str(payload.get("subtype") or "") == "init":
                candidate_session_id = str(payload.get("session_id") or actual_session_id or "").strip()
                if candidate_session_id and not root_session_id:
                    root_session_id = candidate_session_id
                    actual_session_id = candidate_session_id
                    attach_run_session(run_id, actual_session_id)
                    yield {
                        "type": "session",
                        "runId": run_id,
                        "sessionId": actual_session_id,
                        "model": str(payload.get("model") or ""),
                        "permissionMode": str(payload.get("permissionMode") or permission_mode),
                    }
                continue

            if record_type == "stream_event":
                normalized = _normalize_delta_event(payload.get("event") or {})
                if normalized:
                    normalized["runId"] = run_id
                    if actual_session_id:
                        normalized["sessionId"] = actual_session_id
                    yield normalized
                continue

            if record_type == "user" and payload.get("tool_use_result") is not None:
                tool_payload = payload.get("tool_use_result")
                summary = ""
                if isinstance(tool_payload, dict):
                    if tool_payload.get("type") == "update":
                        summary = str(tool_payload.get("filePath") or "")
                    elif tool_payload.get("type") == "text":
                        file_meta = tool_payload.get("file") or {}
                        summary = str(file_meta.get("filePath") or "")
                yield {
                    "type": "tool_result",
                    "runId": run_id,
                    "sessionId": actual_session_id,
                    "summary": summary,
                    "content": payload.get("tool_use_result"),
                    "rawText": normalize_user_content(payload.get("message") or {}),
                }
                continue

            if record_type == "assistant":
                message = payload.get("message") or {}
                content = message.get("content") or []
                tool_uses = [
                    {
                        "id": str(block.get("id") or ""),
                        "name": str(block.get("name") or "工具"),
                        "input": block.get("input") or {},
                    }
                    for block in content
                    if isinstance(block, dict) and str(block.get("type") or "") == "tool_use"
                ]
                if tool_uses:
                    for tool in tool_uses:
                        yield {
                            "type": "tool_snapshot",
                            "runId": run_id,
                            "sessionId": actual_session_id,
                            "tool": tool,
                        }
                continue

            if record_type == "result":
                saw_result = True
                candidate_session_id = str(payload.get("session_id") or actual_session_id or "").strip()
                if candidate_session_id and not root_session_id:
                    root_session_id = candidate_session_id
                actual_session_id = root_session_id or candidate_session_id or actual_session_id
                attach_run_session(run_id, actual_session_id)
                terminal_event_emitted = True
                yield {
                    "type": "done",
                    "runId": run_id,
                    "sessionId": actual_session_id,
                    "result": str(payload.get("result") or ""),
                    "isError": bool(payload.get("is_error")),
                    "stopReason": payload.get("stop_reason"),
                    "durationMs": payload.get("duration_ms"),
                }
                if process.poll() is None:
                    process.terminate()
                break

        try:
            return_code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                process.kill()
            return_code = process.wait(timeout=5)
        if not saw_result and not terminal_event_emitted:
            stderr_text = "\n".join(stderr_lines).strip()
            stopped = False
            with ACTIVE_RUNS_LOCK:
                current = ACTIVE_RUNS.get(run_id)
                if current is not None:
                    stopped = bool(current.get("stopRequested"))
            if stopped:
                yield {"type": "stopped", "runId": run_id, "sessionId": actual_session_id}
            else:
                yield {
                    "type": "done",
                    "runId": run_id,
                    "sessionId": actual_session_id,
                    "result": "",
                    "isError": return_code != 0,
                    "stopReason": "process_exit",
                    "stderr": stderr_text,
                    "durationMs": None,
                }
    finally:
        if process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass
        finish_run(run_id)
