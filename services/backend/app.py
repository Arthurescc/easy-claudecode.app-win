#!/usr/bin/env python3
from __future__ import annotations

import ast
import copy
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from flask import Flask, Response, jsonify, make_response, request, stream_with_context
from werkzeug.exceptions import HTTPException

from claude_console_utils import (
    cleanup_empty_sessions as _claude_cleanup_empty_sessions,
    create_folder as _claude_create_folder,
    delete_session as _claude_delete_session,
    derive_session_title as _claude_derive_session_title,
    derive_session_topic as _claude_derive_session_topic,
    ensure_meta_store as _claude_ensure_meta_store,
    get_session_detail as _claude_get_session_detail,
    list_active_runs as _claude_list_active_runs,
    list_folder_registry as _claude_list_folder_registry,
    list_sessions as _claude_list_sessions,
    project_sessions_dir as _claude_project_sessions_dir,
    rename_folder as _claude_rename_folder,
    save_meta_store as _claude_save_meta_store,
    stop_run as _claude_stop_run,
    run_claude_capture as _claude_run_capture,
    stream_claude_session as _claude_stream_session,
    update_session_meta as _claude_update_session_meta,
)

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent.parent


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, "1" if default else "0") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


EASY_CLAUDECODE_HOME = os.path.expanduser(os.getenv("EASY_CLAUDECODE_HOME", "~/.easy-claudecode"))
EASY_CLAUDECODE_LOG_ROOT = os.path.join(EASY_CLAUDECODE_HOME, "logs")
SOURCE_ROOT = os.path.expanduser(os.getenv("CLAUDE_CONSOLE_SOURCE_ROOT", str(REPO_ROOT)))
EASY_CLAUDECODE_ENV_FILE = os.path.expanduser(
    os.getenv("EASY_CLAUDECODE_ENV_FILE", os.path.join(SOURCE_ROOT, ".env"))
)
FRONTEND_DIR = os.path.expanduser(
    os.getenv("CLAUDE_CONSOLE_FRONTEND_ROOT", os.path.join(SOURCE_ROOT, "apps", "web"))
)
FRONTEND_CLAUDE_CONSOLE_FILE = os.path.join(FRONTEND_DIR, "claude-console.html")
def _resolve_claude_wrapper_path() -> str:
    candidates = [
        os.getenv("CLAUDE_WRAPPER_PATH"),
        shutil.which("claude"),
        "~/.local/node-current/bin/claude",
        "~/.local/bin/claude",
        "~/.local/node-v22.22.0-darwin-arm64/bin/claude",
    ]
    expanded = [os.path.expanduser(str(item or "").strip()) for item in candidates if str(item or "").strip()]
    for candidate in expanded:
        if os.path.exists(candidate):
            return candidate
    for candidate in expanded:
        if candidate:
            return candidate
    return os.path.expanduser("~/.local/node-current/bin/claude")


CLAUDE_WRAPPER_PATH = _resolve_claude_wrapper_path()
CLAUDE_WORKSPACE_ROOT = os.path.expanduser(os.getenv("CLAUDE_WORKSPACE_ROOT", SOURCE_ROOT))
CLAUDE_HOME_DIR = os.path.expanduser(os.getenv("CLAUDE_HOME_DIR", "~/.claude"))
CLAUDE_PROJECT_SESSIONS_DIR = _claude_project_sessions_dir(CLAUDE_HOME_DIR, CLAUDE_WORKSPACE_ROOT)
CLAUDE_CHAT_META_FILE = os.path.expanduser(
    os.getenv("CLAUDE_CHAT_META_FILE", os.path.join(EASY_CLAUDECODE_HOME, "claude-chat-meta.json"))
)
CLAUDE_USER_SETTINGS_FILE = os.path.expanduser(
    os.getenv("CLAUDE_USER_SETTINGS_FILE", "~/.claude.json")
)
CLAUDE_ROUTER_CONFIG_FILE = os.path.expanduser(
    os.getenv("CLAUDE_ROUTER_CONFIG_FILE", os.path.join(EASY_CLAUDECODE_HOME, "router", "config.json"))
)
CLAUDE_ROUTER_CUSTOM_FILE = os.path.expanduser(
    os.getenv("CLAUDE_ROUTER_CUSTOM_FILE", os.path.join(EASY_CLAUDECODE_HOME, "router", "custom-router.js"))
)
CLAUDE_CONSOLE_RUNTIME_ROOT = os.path.expanduser(
    os.getenv("CLAUDE_CONSOLE_RUNTIME_ROOT", os.path.join(EASY_CLAUDECODE_HOME, "runtime", "claude-console"))
)
CLAUDE_CONSOLE_UPLOAD_ROOT = os.path.expanduser(
    os.getenv("CLAUDE_CONSOLE_UPLOAD_ROOT", os.path.join(EASY_CLAUDECODE_HOME, "uploads"))
)
CODEX_HOME = os.path.expanduser(os.getenv("CODEX_HOME", "~/.codex"))
CODEX_AUTOMATIONS_DIR = os.path.join(CODEX_HOME, "automations")
OPENCLAW_HOME_DIR = os.path.expanduser(os.getenv("OPENCLAW_HOME", ""))
OPENCLAW_JOBS_FILE = os.path.expanduser(
    os.getenv("OPENCLAW_JOBS_FILE", os.path.join(OPENCLAW_HOME_DIR, "cron", "jobs.json") if OPENCLAW_HOME_DIR else "")
)
OPENCLAW_BIN = os.path.expanduser(os.getenv("OPENCLAW_BIN", "openclaw"))
CLAUDE_AGENT_DIRS = [
    os.path.join(CLAUDE_HOME_DIR, "agents"),
    os.path.join(SOURCE_ROOT, ".claude", "agents"),
]
CLAUDE_LOCAL_SKILL_DIRS = [
    os.path.join(CLAUDE_HOME_DIR, "skills"),
    os.path.join(SOURCE_ROOT, ".claude", "skills"),
]
CLAUDE_PLUGIN_ROOT = os.path.join(CLAUDE_HOME_DIR, "plugins")
CLAUDE_PLUGIN_INSTALLED_FILE = os.path.join(CLAUDE_PLUGIN_ROOT, "installed_plugins.json")
CLAUDE_PLUGIN_MARKETPLACES_ROOT = os.path.join(CLAUDE_PLUGIN_ROOT, "marketplaces")
CLAUDE_ROUTER_HEALTH_URL = (os.getenv("CLAUDE_ROUTER_HEALTH_URL", "http://127.0.0.1:3456/health") or "").strip()
CLAUDE_PROXY_HEALTH_URL = (os.getenv("CLAUDE_PROXY_HEALTH_URL", "http://127.0.0.1:3460/health") or "").strip()
CLAUDE_ROUTER_WRAPPER_LOG = os.path.expanduser(
    os.getenv("CLAUDE_ROUTER_WRAPPER_LOG", os.path.join(EASY_CLAUDECODE_LOG_ROOT, "claude-code-router-wrapper.log"))
)
CLAUDE_ROUTER_ERR_LOG = os.path.expanduser(
    os.getenv("CLAUDE_ROUTER_ERR_LOG", os.path.join(EASY_CLAUDECODE_LOG_ROOT, "claude-code-router.err.log"))
)
CLAUDE_PROXY_LOG = os.path.expanduser(
    os.getenv("CLAUDE_PROXY_LOG", os.path.join(EASY_CLAUDECODE_LOG_ROOT, "claude-code-dashscope-proxy.log"))
)
CLAUDE_PROXY_ERR_LOG = os.path.expanduser(
    os.getenv("CLAUDE_PROXY_ERR_LOG", os.path.join(EASY_CLAUDECODE_LOG_ROOT, "claude-code-dashscope-proxy.err.log"))
)
CLAUDE_CONSOLE_ERR_LOG = os.path.expanduser(
    os.getenv("CLAUDE_CONSOLE_ERR_LOG", os.path.join(EASY_CLAUDECODE_LOG_ROOT, "claude-console-runtime.error.log"))
)
IS_WINDOWS = os.name == "nt"
CLAUDE_TERMINAL_APP = (os.getenv("CLAUDE_TERMINAL_APP", "powershell" if IS_WINDOWS else "Terminal") or ("powershell" if IS_WINDOWS else "Terminal")).strip()
CLAUDE_TMUX_BIN = os.path.expanduser(os.getenv("CLAUDE_TMUX_BIN", "~/.local/bin/tmux"))
CLAUDE_WEB_PERMISSION_MODE = (os.getenv("CLAUDE_WEB_PERMISSION_MODE", "default") or "default").strip()
CLAUDE_CHAT_TIMEOUT_SECONDS = int(os.getenv("CLAUDE_CHAT_TIMEOUT_SECONDS", "1800"))
CLAUDE_QUICK_RUN_TIMEOUT_SECONDS = int(os.getenv("CLAUDE_QUICK_RUN_TIMEOUT_SECONDS", "180"))
CLAUDE_LIBRARY_CACHE_TTL_SECONDS = float(os.getenv("CLAUDE_LIBRARY_CACHE_TTL_SECONDS", "15"))
CLAUDE_STATUS_CACHE_TTL_SECONDS = float(os.getenv("CLAUDE_STATUS_CACHE_TTL_SECONDS", "4"))
LOCAL_NO_PROXY_VALUE = "127.0.0.1,localhost"
PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
VERSION_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
DIRECT_REPLY_RE = re.compile(r"(只回复|reply with|just say|say only|echo)", re.IGNORECASE)
CLAUDE_EXTRA_ALLOWED_DIRS = [os.path.expanduser(path) for path in _env_list("CLAUDE_EXTRA_ALLOWED_DIRS", [SOURCE_ROOT, os.path.expanduser("~/Desktop")])]
LIBRARY_CACHE_LOCK = threading.Lock()
LIBRARY_CACHE: dict[str, object] = {"signature": None, "payload": None, "createdAt": 0.0}
STATUS_CACHE_LOCK = threading.Lock()
STATUS_CACHE: dict[str, object] = {"payload": None, "createdAt": 0.0}

CLAUDE_MODE_CONFIG = {
    "auto": {
        "label": "Auto",
        "tag": "",
        "description": "按任务内容自动路由到最合适的 Coding Plan 模型",
        "effort": "medium",
        "model": "自动路由",
    },
    "glm5": {
        "label": "glm-5",
        "tag": "[route:glm5]",
        "description": "任务拆解、细节补全、agent teams 编排",
        "effort": "high",
        "model": "glm-5",
    },
    "glm47": {
        "label": "glm-4.7",
        "tag": "[route:glm47]",
        "description": "稳态文本和长对话托底",
        "effort": "medium",
        "model": "glm-4.7",
    },
    "kimi": {
        "label": "kimi-k2.5",
        "tag": "[route:kimi]",
        "description": "截图、OCR、UI、图像理解",
        "effort": "medium",
        "model": "kimi-k2.5",
    },
    "qwenmax": {
        "label": "qwen3-max-2026-01-23",
        "tag": "[route:qwenmax]",
        "description": "复杂推理托底和代码核验",
        "effort": "high",
        "model": "qwen3-max-2026-01-23",
    },
    "qwen35": {
        "label": "qwen3.5-plus",
        "tag": "[route:qwen35]",
        "description": "视觉托底和通用文本补位",
        "effort": "medium",
        "model": "qwen3.5-plus",
    },
    "qwencoder": {
        "label": "qwen3-coder-plus",
        "tag": "[route:qwencoder]",
        "description": "额外编码后备链路",
        "effort": "medium",
        "model": "qwen3-coder-plus",
    },
    "minimax": {
        "label": "MiniMax-M2.7-highspeed",
        "tag": "[route:minimax]",
        "description": "主编程、调试、修复、高逻辑实现",
        "effort": "medium",
        "model": "MiniMax-M2.7-highspeed",
    },
    "opus46": {
        "label": "opus 4.6 thinking",
        "tag": "[route:opus46]",
        "description": "Anthropic 深度思考手动档",
        "effort": "high",
        "model": "claude-opus-4-6-thinking",
    },
}

CLAUDE_ASSIGNMENT_MATRIX = [
    {"scope": "任务拆解 / teams 编排 / 细节补全", "model": "glm-5", "effort": "high"},
    {"scope": "主编程 / 调试 / 实现", "model": "MiniMax-M2.7-highspeed", "effort": "high"},
    {"scope": "审查 / 核验 / 回归", "model": "qwen3-max-2026-01-23", "effort": "high"},
    {"scope": "截图 / OCR / UI / 视觉", "model": "kimi-k2.5", "effort": "medium"},
    {"scope": "视觉托底", "model": "qwen3.5-plus", "effort": "medium"},
    {"scope": "额外编码后备", "model": "qwen3-coder-plus", "effort": "medium"},
]

CLAUDE_AGENT_MODE_CONFIG = {
    "none": {
        "label": "关闭协作",
        "agent": "",
        "description": "不强制使用自定义 agents",
    },
    "auto": {
        "label": "Auto",
        "agent": "task-orchestrator",
        "description": "由 glm-5 先做任务判读，再决定是否分派 specialists",
    },
    "teams": {
        "label": "Agent Teams",
        "agent": "team-orchestrator",
        "description": "复杂任务时并行拉起多个 specialists 协作",
    },
    "subagent": {
        "label": "Subagent",
        "agent": "subagent-coordinator",
        "description": "轻量分派一个主 specialist，必要时再串联验证",
    },
    "coder": {
        "label": "编码代理",
        "agent": "coding-implementer",
        "description": "直接进入强编程实现与排障链",
    },
    "review": {
        "label": "核验代理",
        "agent": "review-verifier",
        "description": "适合审查、核验、回归、diff 检查",
    },
    "vision": {
        "label": "视觉代理",
        "agent": "vision-ui-specialist",
        "description": "适合截图、OCR、UI 与浏览器任务",
    },
    "automation": {
        "label": "自动化代理",
        "agent": "automation-systems-specialist",
        "description": "适合脚本、MCP、守护进程、路由和系统任务",
    },
    "docs": {
        "label": "文档代理",
        "agent": "document-workbench",
        "description": "适合 PDF、Word、PPT、Excel 等交付物",
    },
    "video": {
        "label": "视频代理",
        "agent": "remotion-video-specialist",
        "description": "适合 Remotion、宣传视频、短视频、渲染交付",
    },
}

OPUS46_TEAM_LOCKED_AGENT_MAP = {
    "teams": "team-orchestrator-opus46",
}

OPENCLAW_FIXED_SESSION_KEY = "openclawOps"
CLAUDE_CONSOLE_ENABLE_OPENCLAW = (
    _env_flag("CLAUDE_CONSOLE_ENABLE_EXTERNAL_DISPATCH", False)
    or _env_flag("CLAUDE_CONSOLE_ENABLE_OPENCLAW", False)
)
OPENCLAW_FIXED_SESSION_TITLE = os.getenv("OPENCLAW_FIXED_SESSION_TITLE", "Connected Scheduler")
OPENCLAW_FIXED_SESSION_TOPIC = os.getenv("OPENCLAW_FIXED_SESSION_TOPIC", "Scheduler")
OPENCLAW_FIXED_SESSION_AGENT = os.getenv("OPENCLAW_FIXED_SESSION_AGENT", "openclaw-ops-specialist")
OPENCLAW_FIXED_SESSION_MEMORY_VERSION = os.getenv("OPENCLAW_FIXED_SESSION_MEMORY_VERSION", "public-release")
OPENCLAW_FIXED_SESSION_APP_PATH = os.path.expanduser(os.getenv("OPENCLAW_FIXED_SESSION_APP_PATH", ""))
OPENCLAW_FIXED_SESSION_PATHS = _env_list("OPENCLAW_WORKSPACE_ROOTS", [])
OPENCLAW_TASK_SESSION_ROLE = "openclaw-task"
OPENCLAW_TASK_FOLDER = os.getenv("OPENCLAW_TASK_FOLDER", "External Tasks")
OPENCLAW_SENSITIVE_DOCTRINE_PATH = os.path.expanduser(os.getenv("OPENCLAW_SENSITIVE_DOCTRINE_PATH", ""))
OPENCLAW_SENSITIVE_MANIFEST_PATH = os.path.expanduser(os.getenv("OPENCLAW_SENSITIVE_MANIFEST_PATH", ""))
OPENCLAW_SENSITIVE_BROKER_PATH = os.path.expanduser(os.getenv("OPENCLAW_SENSITIVE_BROKER_PATH", ""))
OPENCLAW_SESSION_TRASH_ROOT = os.path.expanduser("~/.Trash/easy-claudecode-sessions")
OPENCLAW_DISPATCH_LOG_ROOT = os.path.join(CLAUDE_CONSOLE_RUNTIME_ROOT, "logs", "openclaw-dispatch")
OPENCLAW_DISPATCH_STATE_FILE = os.path.join(CLAUDE_CONSOLE_RUNTIME_ROOT, "openclaw-dispatch-state.json")
OPENCLAW_AUTOMATION_TRASH_ROOT = os.path.expanduser("~/.Trash/easy-claudecode-openclaw-cron")
OPENCLAW_DISPATCH_HISTORY_LIMIT = 40
OPENCLAW_DISPATCH_MODE = (os.getenv("OPENCLAW_DISPATCH_MODE", "glm5") or "glm5").strip()
OPENCLAW_DISPATCH_AGENT_MODE = (os.getenv("OPENCLAW_DISPATCH_AGENT_MODE", "teams") or "teams").strip()
OPENCLAW_DISPATCH_AGENT = (os.getenv("OPENCLAW_DISPATCH_AGENT", "team-orchestrator") or "team-orchestrator").strip()
OPENCLAW_MAX_AUTO_TURNS = int(os.getenv("OPENCLAW_MAX_AUTO_TURNS", "20"))
OPENCLAW_DISPATCH_LOCK = threading.Lock()
OPENCLAW_SESSION_LOCK = threading.Lock()
OPENCLAW_DISPATCH_QUEUE: list[dict] = []
OPENCLAW_DISPATCH_ACTIVE: dict[str, dict] = {}
OPENCLAW_DISPATCH_HISTORY: list[dict] = []
OPENCLAW_DISPATCH_WORKERS: dict[str, threading.Thread] = {}
REMOTION_TASK_RE = re.compile(
    r"(remotion|motion graphic|composition|render|promo video|launch video|宣传视频|短视频|片头|片尾|视频动画|做视频|视频渲染|渲染视频|渲染到|出片)",
    re.IGNORECASE,
)
STRONG_CHAT_TASK_RE = re.compile(
    r"(strong programming|high logic|complex|debug|fix|implement|refactor|migration|architecture|self[- ]?heal|self[- ]?repair|coding task|编程|写代码|排障|修复|重构|架构|调试|复杂|高逻辑|高难度|开发软件|做软件|工程任务|自检|自修复)",
    re.IGNORECASE,
)
TEAM_CHAT_TASK_RE = re.compile(
    r"(页面美化|界面美化|逻辑审查|全逻辑|全面.{0,8}(校验|审查|检查|review)|完善.{0,20}\.app|开发.{0,20}\.app|annotator\.app)",
    re.IGNORECASE,
)
COMPLEX_CODE_CHAT_TASK_RE = re.compile(
    r"(complex code|complex software|software task|desktop app|web app|application|full[- ]?stack|frontend|backend|agent teams?|subagent|system design|architecture|"
    r"复杂代码任务|复杂开发|复杂工程|开发软件|做软件|桌面端|网页端|前后端|全链路|完整落地|多代理协作|系统设计|架构设计|大型重构|跨层开发)",
    re.IGNORECASE,
)
CODER_CHAT_TASK_RE = re.compile(
    r"(implement|fix|debug|refactor|migration|build|write code|coding task|代码实现|功能开发|修复bug|修bug|调试|重构|写代码|实现功能)",
    re.IGNORECASE,
)
AUTOMATION_CHAT_TASK_RE = re.compile(
    r"(automation|workflow|cron|launchagent|launchd|service|daemon|router|gateway|bridge|mcp|脚本|自动化|工作流|启动项|守护|路由|网关|桥接)",
    re.IGNORECASE,
)
REVIEW_CHAT_TASK_RE = re.compile(
    r"(review|audit|verify|inspection|check|regression|代码审查|核验|校验|审查|回归检查|逻辑审查)",
    re.IGNORECASE,
)
VISION_CHAT_TASK_RE = re.compile(
    r"(image|screenshot|ocr|vision|ui|figma|界面|截图|图片|视觉|标注|annotator)",
    re.IGNORECASE,
)
DOCUMENT_CHAT_TASK_RE = re.compile(
    r"(pdf|docx|pptx|xlsx|document|report|slides|spreadsheet|文档|报告|表格|幻灯片)",
    re.IGNORECASE,
)
REMOTION_RENDER_WRAPPER = os.path.join(SOURCE_ROOT, "scripts", "remotion-render-with-heartbeat.sh")
for bootstrap_dir in [
    EASY_CLAUDECODE_HOME,
    EASY_CLAUDECODE_LOG_ROOT,
    CLAUDE_CONSOLE_RUNTIME_ROOT,
    CLAUDE_CONSOLE_UPLOAD_ROOT,
    os.path.dirname(CLAUDE_CHAT_META_FILE),
    os.path.dirname(CLAUDE_ROUTER_CONFIG_FILE),
]:
    if bootstrap_dir:
        os.makedirs(bootstrap_dir, exist_ok=True)
CLAUDE_CHAT_RUN_STATE_RE = re.compile(r"<CLAUDE_RUN_STATE>\s*(COMPLETE|CONTINUE|BLOCKED)\s*</CLAUDE_RUN_STATE>", re.IGNORECASE)
CLAUDE_CHAT_COMPLETION_GATE_RE = re.compile(r"<CLAUDE_COMPLETION_GATE>\s*(PASS|FAIL|BLOCKED)\s*</CLAUDE_COMPLETION_GATE>", re.IGNORECASE)
CLAUDE_CHAT_SELFCHECK_RE = re.compile(r"<CLAUDE_SELFCHECK>\s*(PASS|FAIL|BLOCKED)\s*</CLAUDE_SELFCHECK>", re.IGNORECASE)
CLAUDE_CHAT_MAX_AUTO_TURNS = int(os.getenv("CLAUDE_CHAT_MAX_AUTO_TURNS", "24"))
EDITABLE_SETTINGS_FIELDS = (
    "DASHSCOPE_CODINGPLAN_API_KEY",
    "AICODELINK_OPUS46_API_KEY",
    "CLAUDE_DASHSCOPE_PROXY_UPSTREAM",
    "CLAUDE_OPUS_PROXY_UPSTREAM",
    "CLAUDE_ROUTER_HEALTH_URL",
    "CLAUDE_PROXY_HEALTH_URL",
    "CLAUDE_CONSOLE_LOCALE",
)
EDITABLE_SETTINGS_DEFAULTS = {
    "DASHSCOPE_CODINGPLAN_API_KEY": "",
    "AICODELINK_OPUS46_API_KEY": "",
    "CLAUDE_DASHSCOPE_PROXY_UPSTREAM": "https://api.minimaxi.com/anthropic/v1/messages",
    "CLAUDE_OPUS_PROXY_UPSTREAM": "https://aicodelink.shop/v1/messages",
    "CLAUDE_ROUTER_HEALTH_URL": "http://127.0.0.1:3456/health",
    "CLAUDE_PROXY_HEALTH_URL": "http://127.0.0.1:3460/health",
    "CLAUDE_CONSOLE_LOCALE": "zh-CN",
}
ECC_UPSTREAM_REPO_URL = "https://github.com/affaan-m/everything-claude-code.git"
ECC_DEFAULT_TARGET = (os.getenv("EASY_CLAUDECODE_ECC_DEFAULT_TARGET", "claude") or "claude").strip().lower()
ECC_DEFAULT_PROFILE = (os.getenv("EASY_CLAUDECODE_ECC_DEFAULT_PROFILE", "full") or "full").strip().lower()
ECC_INSTALL_SCRIPT = os.path.join(SOURCE_ROOT, "scripts", "install-everything-claude-code.ps1")
ECC_VALID_TARGETS = {"claude", "cursor", "antigravity", "codex", "opencode"}
ECC_VALID_PROFILES = {"core", "developer", "security", "research", "full"}

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="/static")


def _append_runtime_error_log(exc: BaseException) -> None:
    try:
        log_path = Path(CLAUDE_CONSOLE_ERR_LOG)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().isoformat()}] {request.method} {request.path}\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass


def _run_capture(args: list[str], *, cwd: str, timeout: int) -> dict:
    try:
        clean_env = os.environ.copy()
        clean_env["NO_PROXY"] = LOCAL_NO_PROXY_VALUE
        clean_env["no_proxy"] = LOCAL_NO_PROXY_VALUE
        clean_env.setdefault("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", "1")
        for key in PROXY_ENV_KEYS:
            clean_env.pop(key, None)
        completed = subprocess.run(
            args,
            cwd=cwd,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": (completed.stdout or "").strip(),
            "stderr": (completed.stderr or "").strip(),
        }
    except subprocess.TimeoutExpired as exc:
        # exc.stdout/stderr may be bytes even when text=True is used
        stdout_val = exc.stdout
        stderr_val = exc.stderr
        if isinstance(stdout_val, bytes):
            stdout_val = stdout_val.decode("utf-8", errors="replace")
        if isinstance(stderr_val, bytes):
            stderr_val = stderr_val.decode("utf-8", errors="replace")
        return {
            "ok": False,
            "returncode": None,
            "stdout": (stdout_val or "").strip(),
            "stderr": (stderr_val or "").strip(),
            "timedOut": True,
        }
    except Exception as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}


def _resolve_real_claude_bin() -> tuple[bool, str]:
    raw_candidate = str(os.getenv("CLAUDE_REAL_BIN", "claude") or "").strip()
    if not raw_candidate:
        return False, ""
    expanded = os.path.expanduser(raw_candidate)
    if os.path.isabs(expanded) or os.sep in expanded or (IS_WINDOWS and "/" in expanded):
        return os.path.exists(expanded), expanded
    resolved = shutil.which(expanded)
    return bool(resolved), (resolved or expanded)


def _parse_env_assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    return key, value.rstrip("\n")


def _normalize_env_value(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and ((text[0] == text[-1] == '"') or (text[0] == text[-1] == "'")):
        try:
            return ast.literal_eval(text)
        except Exception:
            return text[1:-1]
    return text


def _format_env_value(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    if re.fullmatch(r"[A-Za-z0-9_./:@%+,=\\-]+", text):
        return text
    return shlex.quote(text)


def _load_editable_settings() -> dict[str, str]:
    payload = {key: str(EDITABLE_SETTINGS_DEFAULTS.get(key, "")) for key in EDITABLE_SETTINGS_FIELDS}
    env_path = Path(EASY_CLAUDECODE_ENV_FILE)
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_assignment(line)
            if not parsed:
                continue
            key, raw_value = parsed
            if key in payload:
                payload[key] = _normalize_env_value(raw_value)
    for key in EDITABLE_SETTINGS_FIELDS:
        payload[key] = str(os.getenv(key, payload.get(key, "")) or "")
    return payload


def _save_editable_settings(updates: dict[str, str]) -> None:
    env_path = Path(EASY_CLAUDECODE_ENV_FILE)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True) if env_path.exists() else []
    next_lines: list[str] = []
    touched: set[str] = set()
    for line in existing_lines:
        parsed = _parse_env_assignment(line)
        if not parsed:
            next_lines.append(line)
            continue
        key, _raw_value = parsed
        if key in updates:
            next_lines.append(f"{key}={_format_env_value(updates[key])}\n")
            touched.add(key)
        else:
            next_lines.append(line)
    if next_lines and not next_lines[-1].endswith("\n"):
        next_lines[-1] = next_lines[-1] + "\n"
    for key in EDITABLE_SETTINGS_FIELDS:
        if key in updates and key not in touched:
            next_lines.append(f"{key}={_format_env_value(updates[key])}\n")
    env_path.write_text("".join(next_lines), encoding="utf-8")
    for key, value in updates.items():
        os.environ[key] = str(value or "")


def _sync_router_runtime() -> dict[str, object]:
    script_name = "sync-router.ps1" if IS_WINDOWS else "sync-router.sh"
    script_path = os.path.join(SOURCE_ROOT, "scripts", script_name)
    if not os.path.exists(script_path):
        return {"ok": False, "msg": f"{script_name} not found"}
    if IS_WINDOWS:
        return _run_capture(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            cwd=SOURCE_ROOT,
            timeout=60,
        )
    return _run_capture(["/bin/zsh", script_path], cwd=SOURCE_ROOT, timeout=60)


def _powershell_bin() -> str:
    configured = str(os.getenv("EASY_POWERSHELL_BIN", "") or "").strip()
    if configured:
        return configured
    if shutil.which("pwsh"):
        return "pwsh"
    return "powershell"


def _everything_claude_code_base_payload() -> dict[str, object]:
    return {
        "available": bool(IS_WINDOWS and os.path.exists(ECC_INSTALL_SCRIPT)),
        "optional": True,
        "defaultSelected": False,
        "repoUrl": ECC_UPSTREAM_REPO_URL,
        "target": ECC_DEFAULT_TARGET,
        "profile": ECC_DEFAULT_PROFILE,
        "installed": False,
        "revision": "",
        "repoPath": os.path.join(EASY_CLAUDECODE_HOME, "vendor", "everything-claude-code"),
        "lastInstalledAt": "",
    }


def _everything_claude_code_status() -> dict[str, object]:
    payload = _everything_claude_code_base_payload()
    if not payload["available"]:
        payload["status"] = "unavailable"
        return payload

    result = _run_capture(
        [
            _powershell_bin(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ECC_INSTALL_SCRIPT,
            "-StatusOnly",
            "-Target",
            ECC_DEFAULT_TARGET,
            "-Profile",
            ECC_DEFAULT_PROFILE,
        ],
        cwd=SOURCE_ROOT,
        timeout=60,
    )
    if not result.get("ok"):
        payload["status"] = "error"
        payload["error"] = result.get("stderr") or result.get("stdout") or "status lookup failed"
        return payload

    try:
        status_payload = json.loads(result.get("stdout") or "{}")
        if isinstance(status_payload, dict):
            payload.update(status_payload)
    except Exception:
        payload["status"] = "error"
        payload["error"] = result.get("stdout") or "invalid installer status payload"
        return payload

    payload["status"] = "installed" if payload.get("installed") else "ready"
    return _json_safe(payload)


def _run_everything_claude_code_install(target: str, profile: str) -> dict[str, object]:
    normalized_target = str(target or ECC_DEFAULT_TARGET).strip().lower()
    normalized_profile = str(profile or ECC_DEFAULT_PROFILE).strip().lower()
    if normalized_target not in ECC_VALID_TARGETS:
        raise ValueError(f"unsupported target: {normalized_target}")
    if normalized_profile not in ECC_VALID_PROFILES:
        raise ValueError(f"unsupported profile: {normalized_profile}")
    if not IS_WINDOWS:
        raise RuntimeError("Everything Claude Code installer is only exposed in the Windows app flow")
    if not os.path.exists(ECC_INSTALL_SCRIPT):
        raise FileNotFoundError(ECC_INSTALL_SCRIPT)

    result = _run_capture(
        [
            _powershell_bin(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ECC_INSTALL_SCRIPT,
            "-Target",
            normalized_target,
            "-Profile",
            normalized_profile,
        ],
        cwd=SOURCE_ROOT,
        timeout=3600,
    )
    if not result.get("ok"):
        raise RuntimeError(result.get("stderr") or result.get("stdout") or "Everything Claude Code install failed")

    try:
        payload = json.loads(result.get("stdout") or "{}")
    except Exception:
        payload = {
            "installed": True,
            "target": normalized_target,
            "profile": normalized_profile,
            "output": result.get("stdout") or "",
        }
    if isinstance(payload, dict):
        payload.setdefault("installed", True)
        payload.setdefault("target", normalized_target)
        payload.setdefault("profile", normalized_profile)
    return _json_safe(payload)


def _open_local_path(target: str, *, reveal: bool = False) -> dict[str, object]:
    try:
        if IS_WINDOWS:
            normalized = os.path.normpath(target)
            command = ["explorer", f"/select,{normalized}"] if reveal and os.path.isfile(normalized) else ["explorer", normalized]
        elif sys.platform == "darwin":
            command = ["open", "-R", target] if reveal else ["open", target]
        else:
            command = ["xdg-open", target]
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20)
        if result.returncode != 0:
            return {"ok": False, "msg": result.stderr.strip() or result.stdout.strip() or "open failed"}
        return {"ok": True, "path": target}
    except Exception as exc:
        return {"ok": False, "msg": str(exc)}


def _read_json_file(path: str, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, type(fallback)) else fallback
    except Exception:
        return fallback


def _router_section(router_config: dict) -> dict:
    section = router_config.get("Router")
    if isinstance(section, dict):
        return section
    section = router_config.get("router")
    return section if isinstance(section, dict) else {}


def _router_provider_entries(router_config: dict) -> list[dict]:
    providers = router_config.get("Providers")
    if isinstance(providers, list):
        return [item for item in providers if isinstance(item, dict)]
    providers = router_config.get("providers")
    if isinstance(providers, list):
        return [item for item in providers if isinstance(item, dict)]
    return []


def _json_safe(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _probe_json(url: str, timeout: float = 2.0) -> dict:
    if not url:
        return {"ok": False, "url": url, "status": None, "data": None}
    try:
        parsed = urllib_parse.urlparse(url)
        host = str(parsed.hostname or "").strip().lower()
        opener = (
            urllib_request.build_opener(urllib_request.ProxyHandler({}))
            if host in {"127.0.0.1", "localhost"}
            else urllib_request.build_opener()
        )
        with opener.open(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {"ok": True, "url": url, "status": response.getcode(), "data": payload}
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return {"ok": False, "url": url, "status": exc.code, "data": body}
    except Exception as exc:
        return {"ok": False, "url": url, "status": None, "data": str(exc)}


def _read_tail(path: str, max_bytes: int = 12000) -> dict:
    result = {"exists": os.path.exists(path), "path": path, "size": 0, "text": ""}
    if not result["exists"]:
        return result
    try:
        result["size"] = os.path.getsize(path)
        with open(path, "rb") as f:
            if result["size"] > max_bytes:
                f.seek(-max_bytes, os.SEEK_END)
            result["text"] = f.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        result["text"] = str(exc)
    return result


def _normalize_claude_mode(raw_mode: str | None) -> str:
    mode = (raw_mode or "auto").strip().lower()
    return mode if mode in CLAUDE_MODE_CONFIG else "auto"


def _normalize_agent_mode(raw_mode: str | None) -> str:
    mode = (raw_mode or "auto").strip().lower()
    return mode if mode in CLAUDE_AGENT_MODE_CONFIG else "auto"


def _claude_route_tag(mode: str) -> str:
    return str(CLAUDE_MODE_CONFIG.get(_normalize_claude_mode(mode), {}).get("tag") or "")


def _claude_allowed_dirs() -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for raw_path in [CLAUDE_WORKSPACE_ROOT, *CLAUDE_EXTRA_ALLOWED_DIRS]:
        candidate = os.path.realpath(os.path.expanduser(str(raw_path or "").strip()))
        if not candidate or candidate in seen or not os.path.exists(candidate):
            continue
        seen.add(candidate)
        items.append(candidate)
    return items


def _tmux_binary() -> str:
    candidate = os.path.expanduser(CLAUDE_TMUX_BIN)
    if candidate and os.path.exists(candidate):
        return candidate
    return shutil.which("tmux") or ""


def _tmux_session_name(session_id: str = "", prompt: str = "", continue_latest: bool = False) -> str:
    session_id = str(session_id or "").strip()
    if session_id:
        return f"claude-{session_id[:12]}"
    if continue_latest:
        return "claude-latest"
    title_seed = _claude_derive_session_title(prompt or "claude-session")
    safe_seed = re.sub(r"[^a-zA-Z0-9_-]+", "-", title_seed).strip("-").lower()[:18] or "session"
    return f"claude-{safe_seed}-{datetime.now().strftime('%H%M%S')}"


def _tmux_state() -> dict:
    binary = _tmux_binary()
    payload = {
        "binary": binary or CLAUDE_TMUX_BIN,
        "exists": bool(binary),
        "available": False,
        "sessionCount": 0,
        "sessions": [],
    }
    if not binary:
        return payload
    result = _run_capture(
        [binary, "list-sessions", "-F", "#{session_name}|#{session_windows}|#{session_attached}"],
        cwd=CLAUDE_WORKSPACE_ROOT,
        timeout=3,
    )
    sessions: list[dict[str, object]] = []
    for raw in str(result.get("stdout") or "").splitlines():
        parts = raw.split("|")
        if len(parts) != 3:
            continue
        name, windows, attached = parts
        sessions.append(
            {
                "name": name.strip(),
                "windows": int(windows or 0) if str(windows or "").isdigit() else 0,
                "attached": int(attached or 0) if str(attached or "").isdigit() else 0,
            }
        )
    payload["available"] = True
    payload["sessionCount"] = len(sessions)
    payload["sessions"] = sessions[:12]
    return payload


def _is_opus46_team_lock(mode: str, agent_mode: str, prompt: str = "") -> bool:
    return _normalize_claude_mode(mode) == "opus46" and _normalize_agent_mode(agent_mode) == "teams"


def _resolve_agent_name(agent_mode: str, prompt: str = "", mode: str = "auto") -> str:
    normalized = _resolve_effective_agent_mode(agent_mode, prompt)
    if _is_opus46_team_lock(mode, agent_mode, prompt):
        return OPUS46_TEAM_LOCKED_AGENT_MAP["teams"]
    if REMOTION_TASK_RE.search(str(prompt or "")) and normalized in {"auto", "teams", "subagent"}:
        return "team-orchestrator"
    if (STRONG_CHAT_TASK_RE.search(str(prompt or "")) or TEAM_CHAT_TASK_RE.search(str(prompt or ""))) and normalized == "auto":
        return "team-orchestrator"
    if REMOTION_TASK_RE.search(str(prompt or "")) and normalized == "video":
        return "remotion-video-specialist"
    if DIRECT_REPLY_RE.search(str(prompt or "")) and normalized in {"auto", "teams", "subagent"}:
        return "task-orchestrator"
    return str(CLAUDE_AGENT_MODE_CONFIG.get(normalized, {}).get("agent") or "").strip()


def _resolve_effective_agent_mode(agent_mode: str, prompt: str = "") -> str:
    normalized = _normalize_agent_mode(agent_mode)
    if normalized != "auto":
        return normalized
    text = str(prompt or "").strip()
    if not text or DIRECT_REPLY_RE.search(text):
        return "auto"
    complex_coding = bool(COMPLEX_CODE_CHAT_TASK_RE.search(text))
    if REMOTION_TASK_RE.search(text) or TEAM_CHAT_TASK_RE.search(text):
        return "teams"
    flags = {
        "coding": bool(STRONG_CHAT_TASK_RE.search(text) or CODER_CHAT_TASK_RE.search(text)),
        "automation": bool(AUTOMATION_CHAT_TASK_RE.search(text)),
        "review": bool(REVIEW_CHAT_TASK_RE.search(text)),
        "vision": bool(VISION_CHAT_TASK_RE.search(text)),
        "docs": bool(DOCUMENT_CHAT_TASK_RE.search(text)),
    }
    active = [name for name, enabled in flags.items() if enabled]
    if flags["coding"] and (complex_coding or len(text) >= 180):
        return "teams"
    if len(active) >= 3:
        return "teams"
    if flags["coding"] and (flags["automation"] or flags["review"] or flags["vision"] or flags["docs"]):
        return "teams"
    if flags["automation"] and (flags["review"] or flags["vision"] or flags["docs"]):
        return "teams"
    if flags["vision"] and not flags["coding"] and not flags["automation"] and not flags["review"] and not flags["docs"]:
        return "vision"
    if flags["review"] and not flags["coding"] and not flags["automation"] and not flags["vision"] and not flags["docs"]:
        return "review"
    if flags["docs"] and not flags["coding"] and not flags["automation"] and not flags["vision"]:
        return "docs"
    if flags["automation"] and not flags["coding"] and not flags["review"] and not flags["vision"] and not flags["docs"]:
        return "automation"
    if flags["coding"]:
        return "coder"
    if len(active) >= 2:
        return "subagent"
    if active:
        return "subagent"
    return "auto"


def _resolve_openclaw_dispatch_agent_name(prompt: str) -> str:
    text = str(prompt or "")
    if REMOTION_TASK_RE.search(text):
        return "team-orchestrator"
    return OPENCLAW_DISPATCH_AGENT or OPENCLAW_FIXED_SESSION_AGENT


def _prepare_claude_prompt(prompt: str, mode: str, agent_mode: str = "none") -> str:
    text = (prompt or "").strip()
    if not text:
        return ""
    if "[route:" in text:
        return text
    if DIRECT_REPLY_RE.search(text):
        return text
    complex_code_guard_needed = bool(COMPLEX_CODE_CHAT_TASK_RE.search(text))
    if REMOTION_TASK_RE.search(text) and "[workflow:remotion]" not in text:
        remotion_guard = """
[workflow:remotion]
This is a Remotion video production task.
- If you are in Auto, Agent Teams, or Subagent mode, the lead agent must be `team-orchestrator`, and it must explicitly involve `remotion-video-specialist`, `review-verifier`, and `completion-supervisor`.
- Do not stop at storyboard, script, scene outline, or code-only status.
- If code changes are made in a Remotion project, run the project lint/typecheck before final handoff when practical.
- For real delivery renders, use `{REMOTION_RENDER_WRAPPER} <project_dir> <composition_id> <output_path>` instead of a bare `npx remotion render ...`.
- Do not use a bare `npx remotion render ...` for the final delivery render unless the wrapper script is unavailable.
- Do not wrap the final render command in a pipe such as `| tail`, and do not add a short explicit timeout to the final delivery render.
- Before a delivery render, compare the user request against the current composition config. If the requested duration, output path, format, resolution, or brand brief is already known to mismatch the source, fix the source first instead of rendering a knowingly invalid output.
- A diagnostic test render may be used to expose an unknown runtime error, but it never counts as delivery progress if the output is already known to violate the requested spec.
- You must execute a real Remotion render that writes the requested output file.
- After rendering, verify the output file exists and is usable via file checks such as `ls` or `mdls`.
- When verifying a rendered video, use concrete commands such as `ls -lh <output>`, `mdls -name kMDItemDurationSeconds <output>`, and `file <output>`.
- The verification step must use the correct `mdls` syntax with `-name`; malformed metadata commands do not count as verification.
- If the output file exists but its duration/path/spec does not match the user request, treat the task as unfinished and continue fixing.
- Before stopping, require `review-verifier` and `completion-supervisor` to confirm the requested video was actually rendered and matches the request.
- If `review-verifier` or `completion-supervisor` returns only planning text, zero tool use, or no explicit PASS/FAIL, treat that subagent pass as a no-op and have the lead agent run the missing verification itself before deciding whether to stop.
- If render fails, output is missing, or validation fails, continue fixing and retry rendering instead of stopping.
""".strip()
        text = f"{remotion_guard}\n\n{text}"
    effective_agent_mode = _resolve_effective_agent_mode(agent_mode, text)
    if _is_opus46_team_lock(mode, agent_mode, text) and "[team-route-lock:opus46]" not in text:
        opus_team_lock = """
[team-route-lock:opus46]
- This run is explicitly locked to `opus 4.6 thinking`.
- In Agent Teams mode, every spawned teammate must stay on the same `opus46` route.
- Do not fall back to the default split matrix for this run.
- Use only the `*-opus46` teammate variants so every specialist keeps an isolated context while staying on the same locked model.
""".strip()
        text = f"{opus_team_lock}\n\n{text}"
    if complex_code_guard_needed and "[workflow:complex-code-teams]" not in text:
        complex_code_guard = """
[workflow:complex-code-teams]
This is a complex code or software-delivery task.
- In Auto mode, escalate to official Agent Teams behavior under `team-orchestrator`.
- The team shape should follow the embedded runtime team-context CLAUDE runbook: `product-manager`, `project-manager`, `system-architect`, `ui-ux-designer` when UI is involved, `frontend-engineer`, `backend-engineer`, `qa-engineer`, `review-verifier`, and `completion-supervisor` as needed.
- Each teammate must receive a scoped subtask and keep an isolated context. Do not copy full scratchpads across teammates.
- Do not let multiple implementation agents rewrite the same file concurrently; split file ownership first.
- Preserve user-specified absolute paths exactly. Do not rewrite explicit filesystem targets into repo-relative mirrors.
- A complex code task is unfinished until implementation, QA, independent verification, and completion gate all pass.
- For large or cross-surface development work, all standard team roles must be launched as real teammate sessions before stop/go.
""".strip()
        text = f"{complex_code_guard}\n\n{text}"
    route_tag = _claude_route_tag(mode)
    if not route_tag and effective_agent_mode in {"auto", "teams", "subagent"}:
        route_tag = _claude_route_tag("glm5")
    return f"{route_tag}\n{text}".strip() if route_tag else text


def _should_autocontinue_chat(prompt: str, agent_mode: str = "none") -> bool:
    text = str(prompt or "").strip()
    if not text or DIRECT_REPLY_RE.search(text):
        return False
    normalized_agent_mode = _resolve_effective_agent_mode(agent_mode, text)
    if REMOTION_TASK_RE.search(text):
        return True
    if STRONG_CHAT_TASK_RE.search(text):
        return True
    return normalized_agent_mode in {"teams", "coder", "automation", "video"}


def _prepare_autonomous_chat_prompt(prompt: str) -> str:
    text = str(prompt or "").strip()
    if not text:
        return ""
    guard = """
这是强任务完整落地模式。
- 不要把“已分析”“已定位”“下一步我会继续”当成完成。
- 对实现 / 修复 / 软件开发 / Remotion 渲染 / Agent Teams 协作任务，必须推进到真实产物、自检和完成度门禁都通过才可以停止。
- 如果有产物可以运行、打开、访问、渲染或试用，就必须真实试用，不准只看代码。
- 如果需要多 agent 协作，必须至少包含 implementation、verification、completion gate 三个角色；没有 completion gate 放行，不准结束。
- 每轮末尾必须显式输出以下其一：
  - 完成时：<CLAUDE_RUN_STATE>COMPLETE</CLAUDE_RUN_STATE> <CLAUDE_COMPLETION_GATE>PASS</CLAUDE_COMPLETION_GATE> <CLAUDE_SELFCHECK>PASS</CLAUDE_SELFCHECK>
  - 还需继续时：<CLAUDE_RUN_STATE>CONTINUE</CLAUDE_RUN_STATE> <CLAUDE_COMPLETION_GATE>FAIL</CLAUDE_COMPLETION_GATE> <CLAUDE_SELFCHECK>FAIL</CLAUDE_SELFCHECK>
  - 真阻塞时：<CLAUDE_RUN_STATE>BLOCKED</CLAUDE_RUN_STATE> <CLAUDE_COMPLETION_GATE>BLOCKED</CLAUDE_COMPLETION_GATE> <CLAUDE_SELFCHECK>BLOCKED</CLAUDE_SELFCHECK>
- 如果本轮只完成了探索、定位、部分实现、部分测试或提出下一步计划，统一视为未完成，必须输出 CONTINUE。
""".strip()
    if "[workflow:remotion]" in text:
        guard = (
            f"{guard}\n"
            "- 对 Remotion 任务，真实交付必须包含最终视频文件、输出路径校验、时长校验，以及独立 review-verifier / completion-supervisor 放行。\n"
            "- 对 Remotion 任务，如果从源码就能看出时长、路径、格式或分辨率与要求不符，先修源码再做正式 render；已知错误规格的视频文件不能算有效交付。\n"
            "- 对 Remotion 任务，视频元数据核验优先使用 `ls -lh <output>`、`mdls -name kMDItemDurationSeconds <output>`、`file <output>`；如果某个子代理核验空转，主线程必须自己补完这组核验。"
        )
    return f"{text}\n\n{guard}".strip()


def _safe_filename(name: str) -> str:
    base = Path(str(name or "")).name.strip()
    sanitized = re.sub(r"[^0-9A-Za-z._-]+", "-", base)
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip(".-")
    return sanitized or f"file-{uuid.uuid4().hex[:8]}"


def _load_chat_meta_store() -> dict:
    return _claude_ensure_meta_store(CLAUDE_CHAT_META_FILE)


def _save_chat_meta_store(store: dict) -> None:
    _claude_save_meta_store(CLAUDE_CHAT_META_FILE, store)


def _session_jsonl_path(session_id: str) -> Path:
    return Path(CLAUDE_PROJECT_SESSIONS_DIR) / f"{Path(str(session_id or '')).stem.strip()}.jsonl"


def _resolve_openclaw_fixed_session_id(store: dict | None = None) -> str:
    if not CLAUDE_CONSOLE_ENABLE_OPENCLAW:
        return ""
    meta_store = store or _load_chat_meta_store()
    special_sessions = meta_store.setdefault("specialSessions", {})
    if isinstance(special_sessions, dict):
        candidate = str(special_sessions.get(OPENCLAW_FIXED_SESSION_KEY) or "").strip()
        if candidate and _session_jsonl_path(candidate).exists():
            return candidate
    sessions = meta_store.get("sessions") or {}
    if isinstance(sessions, dict):
        for session_id, meta in sessions.items():
            if not isinstance(meta, dict):
                continue
            if str(meta.get("specialRole") or "").strip() != OPENCLAW_FIXED_SESSION_KEY:
                continue
            candidate = str(session_id or "").strip()
            if candidate and _session_jsonl_path(candidate).exists():
                special_sessions[OPENCLAW_FIXED_SESSION_KEY] = candidate
                _save_chat_meta_store(meta_store)
                return candidate
    return ""


def _apply_openclaw_session_meta(session_id: str, *, store: dict | None = None) -> dict:
    meta_store = store or _load_chat_meta_store()
    sessions = meta_store.setdefault("sessions", {})
    current = sessions.setdefault(session_id, {})
    current["title"] = OPENCLAW_FIXED_SESSION_TITLE
    current["archived"] = False
    current["pinned"] = True
    current["fixed"] = True
    current["specialRole"] = OPENCLAW_FIXED_SESSION_KEY
    current["topic"] = OPENCLAW_FIXED_SESSION_TOPIC
    current["memoryVersion"] = OPENCLAW_FIXED_SESSION_MEMORY_VERSION
    current["updatedAt"] = datetime.now().isoformat()
    current["desktopAppPath"] = OPENCLAW_FIXED_SESSION_APP_PATH
    current["workspaceRoots"] = list(OPENCLAW_FIXED_SESSION_PATHS)
    special_sessions = meta_store.setdefault("specialSessions", {})
    if isinstance(special_sessions, dict):
        special_sessions[OPENCLAW_FIXED_SESSION_KEY] = session_id
    _save_chat_meta_store(meta_store)
    return current


def _openclaw_session_seed_prompt() -> str:
    path_lines = "\n".join(f"- {path}" for path in OPENCLAW_FIXED_SESSION_PATHS)
    return f"""
你现在处在 Claude Code.app 中一个固定、置顶、专门处理外部调度事务的控制会话里。

请把下面这些内容当作外部调度事务体系的长期基础记忆，不要在后续任务里重复追问这些固定事实：

1. 关联桌面 app 是 `{OPENCLAW_FIXED_SESSION_APP_PATH}`。
2. 关联工作路径如下：
{path_lines}
3. 外部调度任务的实际执行发生在 `{OPENCLAW_TASK_FOLDER}` 文件夹下按来源拆分的任务线程里，而不是把所有任务都塞回这个固定控制会话。
4. 这个控制会话用于保存长期背景、固定路径和统一工作方式；真正的强任务会被投递到不同任务线程里并可并发执行。
5. 遇到复杂工程任务时，你可以主动编排 coding / automation / review 方向的协作，但最终要在当前任务线程内把结果做完。
6. 默认工作方式是直接推进、直接落地、直接验证，不要把这类事务退回成泛泛讨论。
7. 涉及敏感隐私信息时先拒绝：密码、API key、token、cookie、session、appSecret、verificationToken、encryptKey、`.env`、私有配置、私有启动项默认不直接展示、不直接发送。
8. 如果端侧确实要拿敏感文件，只允许走本地 broker：`{OPENCLAW_SENSITIVE_BROKER_PATH}`；没有密码校验，不允许解封或外发。
9. 敏感隐私规则参考：`{OPENCLAW_SENSITIVE_DOCTRINE_PATH}` 与 `{OPENCLAW_SENSITIVE_MANIFEST_PATH}`。

现在只回复 `SCHEDULER_SESSION_READY`，不要输出别的内容。
""".strip()


OPENCLAW_DISPATCH_PREFIX_RE = re.compile(
    r"^(?:\[[^\]]+\]\s*)?(?:(?:这|这是|属于|按|作为)\s*)?(?:(?:一个|类)\s*)?(?:强编程|高逻辑|高难度复杂|自修复|自进化|失败链治理)(?:任务|模式)?[\s，,：:]*",
    re.IGNORECASE,
)
OPENCLAW_RUN_STATE_RE = re.compile(r"<OPENCLAW_RUN_STATE>\s*(COMPLETE|CONTINUE|BLOCKED)\s*</OPENCLAW_RUN_STATE>", re.IGNORECASE)
OPENCLAW_COMPLETION_GATE_RE = re.compile(r"<OPENCLAW_COMPLETION_GATE>\s*(PASS|FAIL|BLOCKED)\s*</OPENCLAW_COMPLETION_GATE>", re.IGNORECASE)
OPENCLAW_SELFCHECK_RE = re.compile(r"<OPENCLAW_SELFCHECK>\s*(PASS|FAIL|BLOCKED)\s*</OPENCLAW_SELFCHECK>", re.IGNORECASE)
OPENCLAW_WAITING_RE = re.compile(
    r"(等待(?:下一步|进一步)?指令|等待用户|如需继续|如果你需要|如果需要我继续|需要你确认|请告诉我下一步|awaiting|waiting for|let me know)",
    re.IGNORECASE,
)


def _normalize_openclaw_dispatch_task(prompt: str) -> tuple[str, str]:
    raw = str(prompt or "").strip()
    if not raw:
        return "", ""
    normalized = OPENCLAW_DISPATCH_PREFIX_RE.sub("", raw, count=1).strip()
    normalized = re.sub(r"^\s*(?:请你|请|直接|现在)\s*", "", normalized).strip()
    normalized = normalized.lstrip("，,。:：;；- ").strip()
    if not normalized:
        normalized = raw
    return raw, normalized


def _compose_openclaw_dispatch_prompt(
    prompt: str,
    *,
    source: str,
    route_key: str = "",
    openclaw_session_id: str = "",
    openclaw_message_id: str = "",
    sender_label: str = "",
) -> str:
    raw_task, normalized_task = _normalize_openclaw_dispatch_task(prompt)
    lines = [
        "这是来自外部入口或调度器的强编程事务投递，请在当前独立任务线程中继续处理。",
        "",
        "严格执行规则：",
        "1. 你必须优先读取 <OPENCLAW_TASK> 标签内的任务正文；只要该任务正文非空，就立即开始执行，不准回复“任务为空”“是否测试投递”或类似确认语。",
        "2. 如果原文开头带有“这是一个强编程任务 / 高逻辑任务 / 自修复任务”等字样，把这视为路由标签，不是空任务，不要把后续正文丢掉。",
        "3. 默认直接开始第一轮实现、排障、验证和落盘；只有在缺少不可推断且阻塞执行的关键输入时，才允许在完成一轮本地尝试后提出最多 3 个缺口。",
        "4. <OPENCLAW_RAW_TASK> 只是原文备查，真正应该执行的是 <OPENCLAW_TASK>。",
        "5. 对明确的强编程 / 高复杂工程任务，默认采用 agent teams 工作方式：至少形成 implementation、verification、completion gate 三条协作链。不同 specialists 可以并发，但最终必须汇总到当前线程。",
        "6. `completion-supervisor` 是强制停机门禁。没有它的明确放行，不准把任务当成完成。",
        "7. 只要产物可以被打开、运行、访问或试用，就必须实际做一轮自检试用，而不是只看代码或文件。",
        "8. 这是自治执行模式：如果本轮做不完，不要停在“等待下一步指令”。必须在本轮末尾输出 `<OPENCLAW_RUN_STATE>CONTINUE</OPENCLAW_RUN_STATE>`，系统会自动续跑下一轮。",
        "9. 只有真正完成整个任务、`completion-supervisor` 明确放行、且自检试用通过时，才同时输出 `<OPENCLAW_RUN_STATE>COMPLETE</OPENCLAW_RUN_STATE>`、`<OPENCLAW_COMPLETION_GATE>PASS</OPENCLAW_COMPLETION_GATE>`、`<OPENCLAW_SELFCHECK>PASS</OPENCLAW_SELFCHECK>`。",
        "10. 如果还没做完、测试不稳、验收未过、缺少监督放行，统一输出 `<OPENCLAW_RUN_STATE>CONTINUE</OPENCLAW_RUN_STATE>`、`<OPENCLAW_COMPLETION_GATE>FAIL</OPENCLAW_COMPLETION_GATE>`、`<OPENCLAW_SELFCHECK>FAIL</OPENCLAW_SELFCHECK>`。",
        "11. 只有缺少不可推断且阻塞执行的关键信息时，才输出 `<OPENCLAW_RUN_STATE>BLOCKED</OPENCLAW_RUN_STATE>`，并输出 `<OPENCLAW_COMPLETION_GATE>BLOCKED</OPENCLAW_COMPLETION_GATE>`、`<OPENCLAW_SELFCHECK>BLOCKED</OPENCLAW_SELFCHECK>` 说明缺口。",
        "12. 遇到敏感隐私信息请求时先拒绝：密码、API key、token、cookie、session、appSecret、verificationToken、encryptKey、`.env`、私有配置、私有启动项默认不直接展示、不直接发送。",
        f"13. 如果任务硬要走到导出 / 发文件 / 发文档这一步，必须先要求端侧通过 `{OPENCLAW_SENSITIVE_BROKER_PATH}` 做密码校验；没有 broker 通过结果，一律拒绝继续。",
        "",
        f"来源: {source}",
    ]
    if openclaw_session_id:
        lines.append(f"Scheduler session: {openclaw_session_id}")
    if openclaw_message_id:
        lines.append(f"Scheduler message: {openclaw_message_id}")
    if sender_label:
        lines.append(f"Sender: {sender_label}")
    lines.extend(
        [
            "",
            "处理要求：",
            "- 这是强编程 / 工程实现链，优先直接落地，不要空谈。",
            "- 默认可使用本机可信目录与全权限执行链。",
            "- 若需要协作，自行调度 coding / automation / review / completion-supervisor 方向，但保持当前任务线程连续。",
            "- 当前线程是独立隔离的任务会话，不要把别的线程内容串进来。",
            "",
            "<OPENCLAW_TASK>",
            normalized_task,
            "</OPENCLAW_TASK>",
            "",
            "<OPENCLAW_RAW_TASK>",
            raw_task,
            "</OPENCLAW_RAW_TASK>",
        ]
    )
    if route_key:
        lines.insert(lines.index("") + 1, f"当前任务隔离标识: {route_key}")
    return "\n".join(lines).strip()


def _dispatch_preview(text: str, limit: int = 160) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _derive_openclaw_task_title(prompt: str, sender_label: str = "") -> str:
    raw_task, normalized_task = _normalize_openclaw_dispatch_task(prompt)
    seed = normalized_task or raw_task or sender_label or "工程任务"
    title = _claude_derive_session_title(seed)
    if title == "新对话" and sender_label:
        title = _claude_derive_session_title(sender_label)
    return title or "工程任务"


def _derive_openclaw_task_topic(prompt: str) -> str:
    raw_task, normalized_task = _normalize_openclaw_dispatch_task(prompt)
    return _claude_derive_session_topic(normalized_task or raw_task or "工程任务")


def _apply_openclaw_task_session_meta(
    session_id: str,
    *,
    prompt: str,
    sender_label: str = "",
    source: str = "",
    openclaw_session_id: str = "",
    route_key: str = "",
) -> dict:
    meta_store = _load_chat_meta_store()
    sessions = meta_store.setdefault("sessions", {})
    current = sessions.setdefault(session_id, {})
    current["title"] = _derive_openclaw_task_title(prompt, sender_label)
    current["folder"] = OPENCLAW_TASK_FOLDER
    current["topic"] = _derive_openclaw_task_topic(prompt)
    current["archived"] = False
    current["pinned"] = False
    current["fixed"] = False
    current["specialRole"] = OPENCLAW_TASK_SESSION_ROLE
    current["updatedAt"] = datetime.now().isoformat()
    current["originSource"] = source
    current["originOpenclawSessionId"] = openclaw_session_id
    current["routeKey"] = route_key
    _save_chat_meta_store(meta_store)
    return current


def _resolve_openclaw_task_binding(route_key: str, session_id: str) -> str:
    safe_route_key = str(route_key or "").strip()
    safe_session_id = str(session_id or "").strip()
    if not safe_route_key or not safe_session_id:
        return ""
    session_path = _session_jsonl_path(safe_session_id)
    if not session_path.exists():
        return ""
    meta_store = _load_chat_meta_store()
    meta = (meta_store.get("sessions") or {}).get(safe_session_id, {})
    if not isinstance(meta, dict):
        return ""
    if str(meta.get("specialRole") or "").strip() != OPENCLAW_TASK_SESSION_ROLE:
        return ""
    if str(meta.get("routeKey") or "").strip() != safe_route_key:
        return ""
    return safe_session_id


def _parse_openclaw_run_state(result_text: str, *, is_error: bool = False, stderr_text: str = "") -> str:
    text = str(result_text or "")
    match = OPENCLAW_RUN_STATE_RE.search(text)
    gate_match = OPENCLAW_COMPLETION_GATE_RE.search(text)
    selfcheck_match = OPENCLAW_SELFCHECK_RE.search(text)
    gate = str(gate_match.group(1) or "").upper() if gate_match else ""
    selfcheck = str(selfcheck_match.group(1) or "").upper() if selfcheck_match else ""
    if match:
        state = str(match.group(1) or "").upper()
        if state == "COMPLETE":
            return "COMPLETE" if gate == "PASS" and selfcheck == "PASS" else "CONTINUE"
        if state == "BLOCKED":
            return "BLOCKED" if gate == "BLOCKED" and selfcheck == "BLOCKED" else "CONTINUE"
        return "CONTINUE"
    if is_error:
        return "CONTINUE"
    if OPENCLAW_WAITING_RE.search(text):
        return "CONTINUE"
    if stderr_text and not text:
        return "CONTINUE"
    # Strong-task dispatches must emit explicit completion markers.
    # Plain summaries, silent stream exits, or partial reports are treated as unfinished.
    return "CONTINUE"


def _parse_autonomous_chat_run_state(result_text: str, *, is_error: bool = False, stderr_text: str = "") -> str:
    text = str(result_text or "")
    match = CLAUDE_CHAT_RUN_STATE_RE.search(text)
    gate_match = CLAUDE_CHAT_COMPLETION_GATE_RE.search(text)
    selfcheck_match = CLAUDE_CHAT_SELFCHECK_RE.search(text)
    gate = str(gate_match.group(1) or "").upper() if gate_match else ""
    selfcheck = str(selfcheck_match.group(1) or "").upper() if selfcheck_match else ""
    if match:
        state = str(match.group(1) or "").upper()
        if state == "COMPLETE":
            return "COMPLETE" if gate == "PASS" and selfcheck == "PASS" else "CONTINUE"
        if state == "BLOCKED":
            return "BLOCKED" if gate == "BLOCKED" and selfcheck == "BLOCKED" else "CONTINUE"
        return "CONTINUE"
    if is_error:
        return "CONTINUE"
    if OPENCLAW_WAITING_RE.search(text):
        return "CONTINUE"
    if stderr_text and not text:
        return "CONTINUE"
    return "CONTINUE"


def _build_autonomous_chat_continue_prompt(*, original_prompt: str, turn_index: int, last_result: str = "", last_error: str = "") -> str:
    lines = [
        "继续同一强任务，直接推进未完成部分。",
        f"当前是自动续跑第 {turn_index} 轮。",
        "不要重复总结已完成内容，不要停在计划或下一步说明。",
        "如果实现、渲染、运行、自检或 completion gate 仍未全部通过，本轮末尾必须输出 <CLAUDE_RUN_STATE>CONTINUE</CLAUDE_RUN_STATE> <CLAUDE_COMPLETION_GATE>FAIL</CLAUDE_COMPLETION_GATE> <CLAUDE_SELFCHECK>FAIL</CLAUDE_SELFCHECK>。",
        "只有真正完整交付并通过独立核验时，才输出 <CLAUDE_RUN_STATE>COMPLETE</CLAUDE_RUN_STATE> <CLAUDE_COMPLETION_GATE>PASS</CLAUDE_COMPLETION_GATE> <CLAUDE_SELFCHECK>PASS</CLAUDE_SELFCHECK>。",
        "只有缺少不可推断且阻塞执行的关键输入时，才输出 <CLAUDE_RUN_STATE>BLOCKED</CLAUDE_RUN_STATE> <CLAUDE_COMPLETION_GATE>BLOCKED</CLAUDE_COMPLETION_GATE> <CLAUDE_SELFCHECK>BLOCKED</CLAUDE_SELFCHECK>。",
        "如果产物可以真实打开、访问、运行、渲染或试用，本轮必须做实际自检再决定是否完成。",
    ]
    if REMOTION_TASK_RE.search(original_prompt):
        lines.append("对当前 Remotion 任务，继续直到实际写出目标视频文件、校验时长、并得到 review-verifier 与 completion-supervisor 放行。")
    if last_error:
        lines.extend(["", "上一轮错误 / 中断：", _dispatch_preview(last_error, 500)])
    elif last_result:
        lines.extend(["", "上一轮摘要：", _dispatch_preview(last_result, 500)])
    return "\n".join(lines).strip()


def _build_openclaw_continue_prompt(item: dict, *, turn_index: int, last_result: str = "", last_error: str = "") -> str:
    lines = [
        "继续同一强工程任务，直接推进未完成部分。",
        f"当前是自动续跑第 {turn_index} 轮。",
        "不要重复总结已完成内容，不要等待新的用户指令。",
        "注意：没有显式 PASS 标记，系统不会把本轮当作完成。",
        "如果本轮后仍未完成，必须输出 <OPENCLAW_RUN_STATE>CONTINUE</OPENCLAW_RUN_STATE>、<OPENCLAW_COMPLETION_GATE>FAIL</OPENCLAW_COMPLETION_GATE>、<OPENCLAW_SELFCHECK>FAIL</OPENCLAW_SELFCHECK>。",
        "真正完成整个任务时输出 <OPENCLAW_RUN_STATE>COMPLETE</OPENCLAW_RUN_STATE>、<OPENCLAW_COMPLETION_GATE>PASS</OPENCLAW_COMPLETION_GATE>、<OPENCLAW_SELFCHECK>PASS</OPENCLAW_SELFCHECK>。",
        "只有缺少不可推断且阻塞执行的关键输入时输出 <OPENCLAW_RUN_STATE>BLOCKED</OPENCLAW_RUN_STATE>、<OPENCLAW_COMPLETION_GATE>BLOCKED</OPENCLAW_COMPLETION_GATE>、<OPENCLAW_SELFCHECK>BLOCKED</OPENCLAW_SELFCHECK>。",
        "如果 review-verifier 或 completion-supervisor 仍发现缺口，就继续修，不准提前结束。",
        "如果产物可以被真实打开、运行或访问，本轮必须做试用自检，再决定是否完成。",
    ]
    if last_error:
        lines.extend(["", "上一轮错误 / 中断：", _dispatch_preview(last_error, 400)])
    elif last_result:
        lines.extend(["", "上一轮摘要：", _dispatch_preview(last_result, 400)])
    return "\n".join(lines).strip()


def _load_initial_dispatch_state() -> tuple[dict[str, str], list[dict]]:
    if not CLAUDE_CONSOLE_ENABLE_OPENCLAW:
        return {}, []
    path = Path(OPENCLAW_DISPATCH_STATE_FILE)
    if not path.exists():
        return {}, []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, []
    bindings = payload.get("bindings") if isinstance(payload, dict) else {}
    history = payload.get("history") if isinstance(payload, dict) else []
    return (
        {str(key): str(value) for key, value in (bindings or {}).items() if str(key).strip() and str(value).strip()},
        list(history or []),
    )


OPENCLAW_ROUTE_BINDINGS, OPENCLAW_DISPATCH_HISTORY = _load_initial_dispatch_state()


def _dispatch_state_snapshot_locked() -> dict:
    if not CLAUDE_CONSOLE_ENABLE_OPENCLAW:
        return {
            "updatedAt": datetime.now().isoformat(),
            "queueLength": 0,
            "queue": [],
            "active": None,
            "activeCount": 0,
            "activeItems": [],
            "bindings": {},
            "history": [],
        }
    queue_items = [
        {
            "dispatchId": item.get("dispatchId"),
            "routeKey": item.get("routeKey"),
            "source": item.get("source"),
            "createdAt": item.get("createdAt"),
            "sessionId": item.get("sessionId"),
            "preview": item.get("preview"),
            "attempts": item.get("attempts", 0),
        }
        for item in OPENCLAW_DISPATCH_QUEUE
    ]
    active_items = [
        {
            "dispatchId": item.get("dispatchId"),
            "routeKey": route_key,
            "source": item.get("source"),
            "startedAt": item.get("startedAt"),
            "sessionId": item.get("sessionId"),
            "preview": item.get("preview"),
            "attempts": item.get("attempts", 0),
        }
        for route_key, item in OPENCLAW_DISPATCH_ACTIVE.items()
    ]
    active_items.sort(key=lambda item: str(item.get("startedAt") or ""))
    active_item = active_items[0] if active_items else None
    return {
        "updatedAt": datetime.now().isoformat(),
        "queueLength": len(queue_items),
        "queue": queue_items,
        "active": active_item,
        "activeCount": len(active_items),
        "activeItems": active_items,
        "bindings": dict(OPENCLAW_ROUTE_BINDINGS),
        "history": list(OPENCLAW_DISPATCH_HISTORY[-OPENCLAW_DISPATCH_HISTORY_LIMIT:]),
    }


def _combined_active_runs() -> list[dict]:
    active_runs = list(_claude_list_active_runs() or [])
    if not CLAUDE_CONSOLE_ENABLE_OPENCLAW:
        return active_runs
    seen_ids = {
        str(item.get("runId") or item.get("id") or item.get("sessionId") or "").strip()
        for item in active_runs
        if isinstance(item, dict)
    }
    with OPENCLAW_DISPATCH_LOCK:
        active_items = [
            {
                "runId": str(item.get("dispatchId") or route_key or "").strip(),
                "id": str(item.get("dispatchId") or route_key or "").strip(),
                "sessionId": str(item.get("sessionId") or "").strip(),
                "routeKey": route_key,
                "source": str(item.get("source") or "openclaw-dispatch"),
                "preview": str(item.get("preview") or ""),
                "startedAt": str(item.get("startedAt") or ""),
                "status": "running",
                "kind": "openclaw-dispatch",
            }
            for route_key, item in OPENCLAW_DISPATCH_ACTIVE.items()
        ]
    for item in active_items:
        run_id = str(item.get("runId") or item.get("id") or item.get("sessionId") or "").strip()
        if not run_id or run_id in seen_ids:
            continue
        active_runs.append(item)
        seen_ids.add(run_id)
    return active_runs


def _find_session_active_run(session_id: str) -> dict | None:
    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        return None
    for item in _combined_active_runs():
        if not isinstance(item, dict):
            continue
        if str(item.get("sessionId") or "").strip() != safe_session_id:
            continue
        return {
            "runId": str(item.get("runId") or item.get("id") or "").strip(),
            "kind": str(item.get("kind") or "claude-run").strip() or "claude-run",
            "source": str(item.get("source") or "").strip(),
            "startedAt": str(item.get("startedAt") or "").strip(),
            "preview": _dispatch_preview(str(item.get("preview") or item.get("prompt") or ""), 160),
        }
    return None


def _save_dispatch_state_locked() -> None:
    if not CLAUDE_CONSOLE_ENABLE_OPENCLAW:
        return
    state_path = Path(OPENCLAW_DISPATCH_STATE_FILE)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(_dispatch_state_snapshot_locked(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_dispatch_history_locked(item: dict) -> None:
    OPENCLAW_DISPATCH_HISTORY.append(item)
    if len(OPENCLAW_DISPATCH_HISTORY) > OPENCLAW_DISPATCH_HISTORY_LIMIT:
        del OPENCLAW_DISPATCH_HISTORY[:-OPENCLAW_DISPATCH_HISTORY_LIMIT]


def _ensure_openclaw_fixed_session(force_reseed: bool = False) -> dict:
    if not CLAUDE_CONSOLE_ENABLE_OPENCLAW:
        return {"ok": False, "created": False, "disabled": True, "sessionId": "", "meta": {}}
    with OPENCLAW_SESSION_LOCK:
        meta_store = _load_chat_meta_store()
        session_id = "" if force_reseed else _resolve_openclaw_fixed_session_id(meta_store)
        if session_id:
            meta = _apply_openclaw_session_meta(session_id, store=meta_store)
            return {"ok": True, "created": False, "sessionId": session_id, "meta": meta}

        prepared_prompt = f"{_claude_route_tag('glm5')}\n{_openclaw_session_seed_prompt()}".strip()
        actual_session_id = ""
        final_result = ""
        final_error = ""
        for event in _claude_stream_session(
            CLAUDE_WRAPPER_PATH,
            CLAUDE_WORKSPACE_ROOT,
            prepared_prompt,
            session_id=None,
            agent_name=OPENCLAW_FIXED_SESSION_AGENT,
            permission_mode=CLAUDE_WEB_PERMISSION_MODE,
            add_dirs=_claude_allowed_dirs(),
            timeout_seconds=CLAUDE_CHAT_TIMEOUT_SECONDS,
        ):
            if event.get("type") == "session":
                actual_session_id = str(event.get("sessionId") or "").strip()
            elif event.get("type") == "done":
                final_result = str(event.get("result") or "").strip()
                final_error = str(event.get("stderr") or "").strip()
                if event.get("isError"):
                    raise RuntimeError(final_error or final_result or "Scheduler fixed session seed failed")

        if not actual_session_id:
            raise RuntimeError("Scheduler fixed session was not created")

        meta_store = _load_chat_meta_store()
        meta = _apply_openclaw_session_meta(actual_session_id, store=meta_store)
        return {
            "ok": True,
            "created": True,
            "sessionId": actual_session_id,
            "meta": meta,
            "seedReply": final_result or final_error,
        }


def _next_openclaw_dispatch_for_route_locked(route_key: str) -> dict | None:
    for index, item in enumerate(OPENCLAW_DISPATCH_QUEUE):
        if str(item.get("routeKey") or "") != route_key:
            continue
        return OPENCLAW_DISPATCH_QUEUE.pop(index)
    return None


def _bind_openclaw_route_session(route_key: str, session_id: str) -> None:
    safe_route_key = str(route_key or "").strip()
    safe_session_id = str(session_id or "").strip()
    if not safe_route_key or not safe_session_id:
        return
    with OPENCLAW_DISPATCH_LOCK:
        OPENCLAW_ROUTE_BINDINGS[safe_route_key] = safe_session_id
        _save_dispatch_state_locked()


def _run_openclaw_dispatch_turn(item: dict, *, prompt: str, session_id: str = "") -> dict:
    actual_session_id = session_id
    result_text = ""
    stderr_text = ""
    is_error = False
    model_name = ""
    agent_name = _resolve_openclaw_dispatch_agent_name(str(item.get("prompt") or prompt or ""))
    for event in _claude_stream_session(
        CLAUDE_WRAPPER_PATH,
        CLAUDE_WORKSPACE_ROOT,
        prompt,
        session_id=session_id or None,
        agent_name=agent_name,
        permission_mode=CLAUDE_WEB_PERMISSION_MODE,
        add_dirs=_claude_allowed_dirs(),
        timeout_seconds=CLAUDE_CHAT_TIMEOUT_SECONDS,
    ):
        if event.get("type") == "session":
            actual_session_id = str(event.get("sessionId") or actual_session_id or "").strip()
            model_name = str(event.get("model") or model_name or "").strip()
        elif event.get("type") == "done":
            result_text = str(event.get("result") or "").strip()
            stderr_text = str(event.get("stderr") or "").strip()
            is_error = bool(event.get("isError"))
    return {
        "sessionId": actual_session_id,
        "result": result_text,
        "stderr": stderr_text,
        "isError": is_error,
        "model": model_name,
        "agent": agent_name,
    }


def _run_openclaw_dispatch_item(item: dict) -> dict:
    route_key = str(item.get("routeKey") or item.get("dispatchId") or "").strip()
    bound_session_id = str(item.get("claudeSessionId") or "").strip()
    if not bound_session_id and route_key:
        bound_session_id = str(OPENCLAW_ROUTE_BINDINGS.get(route_key) or "").strip()
    if route_key:
        bound_session_id = _resolve_openclaw_task_binding(route_key, bound_session_id)

    first_turn_prompt = _prepare_claude_prompt(
        _compose_openclaw_dispatch_prompt(
            str(item.get("prompt") or ""),
            source=str(item.get("source") or "openclaw"),
            route_key=route_key,
            openclaw_session_id=str(item.get("openclawSessionId") or ""),
            openclaw_message_id=str(item.get("openclawMessageId") or ""),
            sender_label=str(item.get("senderLabel") or ""),
        ),
        OPENCLAW_DISPATCH_MODE,
        OPENCLAW_DISPATCH_AGENT_MODE,
    )

    actual_session_id = bound_session_id
    final_result = ""
    final_error = ""
    final_model = ""
    final_state = "CONTINUE"
    turn_results: list[dict] = []
    next_prompt = first_turn_prompt

    for turn_index in range(1, OPENCLAW_MAX_AUTO_TURNS + 1):
        turn = _run_openclaw_dispatch_turn(item, prompt=next_prompt, session_id=actual_session_id)
        actual_session_id = str(turn.get("sessionId") or actual_session_id or "").strip()
        final_result = str(turn.get("result") or "").strip()
        final_error = str(turn.get("stderr") or "").strip()
        final_model = str(turn.get("model") or final_model or "").strip()
        final_state = _parse_openclaw_run_state(
            final_result,
            is_error=bool(turn.get("isError")),
            stderr_text=final_error,
        )
        turn_results.append(
            {
                "turn": turn_index,
                "sessionId": actual_session_id,
                "agent": str(turn.get("agent") or ""),
                "model": final_model,
                "runState": final_state,
                "isError": bool(turn.get("isError")),
                "resultPreview": _dispatch_preview(final_result, 240),
                "stderrPreview": _dispatch_preview(final_error, 240),
            }
        )
        if actual_session_id:
            _apply_openclaw_task_session_meta(
                actual_session_id,
                prompt=str(item.get("prompt") or ""),
                sender_label=str(item.get("senderLabel") or ""),
                source=str(item.get("source") or ""),
                openclaw_session_id=str(item.get("openclawSessionId") or ""),
                route_key=route_key,
            )
            if route_key:
                _bind_openclaw_route_session(route_key, actual_session_id)
        if final_state != "CONTINUE":
            break
        next_prompt = _prepare_claude_prompt(
            _build_openclaw_continue_prompt(
                item,
                turn_index=turn_index + 1,
                last_result=final_result,
                last_error=final_error,
            ),
            OPENCLAW_DISPATCH_MODE,
            OPENCLAW_DISPATCH_AGENT_MODE,
        )

    if final_state == "CONTINUE":
        final_state = "BLOCKED"
        final_error = (final_error + "\n" if final_error else "") + f"auto-turn limit reached ({OPENCLAW_MAX_AUTO_TURNS})"

    Path(OPENCLAW_DISPATCH_LOG_ROOT).mkdir(parents=True, exist_ok=True)
    log_path = Path(OPENCLAW_DISPATCH_LOG_ROOT) / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{item['dispatchId']}.json"
    payload = {
        "dispatchId": item["dispatchId"],
        "routeKey": route_key,
        "createdAt": item["createdAt"],
        "startedAt": item.get("startedAt"),
        "finishedAt": datetime.now().isoformat(),
        "sessionId": actual_session_id,
        "source": item.get("source"),
        "openclawSessionId": item.get("openclawSessionId"),
        "openclawMessageId": item.get("openclawMessageId"),
        "senderLabel": item.get("senderLabel"),
        "prompt": item.get("prompt"),
        "preparedPrompt": first_turn_prompt,
        "agent": turn_results[-1].get("agent") if turn_results else _resolve_openclaw_dispatch_agent_name(str(item.get("prompt") or "")),
        "model": final_model,
        "ok": final_state == "COMPLETE",
        "runState": final_state,
        "turnCount": len(turn_results),
        "turns": turn_results,
        "result": final_result,
        "stderr": final_error,
    }
    log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["logPath"] = str(log_path)
    return payload


def _openclaw_dispatch_worker(route_key: str) -> None:
    while True:
        with OPENCLAW_DISPATCH_LOCK:
            item = _next_openclaw_dispatch_for_route_locked(route_key)
            if item is None:
                OPENCLAW_DISPATCH_ACTIVE.pop(route_key, None)
                OPENCLAW_DISPATCH_WORKERS.pop(route_key, None)
                _save_dispatch_state_locked()
                return
            item["startedAt"] = datetime.now().isoformat()
            item["attempts"] = int(item.get("attempts") or 0) + 1
            OPENCLAW_DISPATCH_ACTIVE[route_key] = item
            _save_dispatch_state_locked()

        try:
            result = _run_openclaw_dispatch_item(item)
        except Exception as exc:  # noqa: BLE001
            result = {
                "dispatchId": item["dispatchId"],
                "routeKey": route_key,
                "createdAt": item.get("createdAt"),
                "startedAt": item.get("startedAt"),
                "finishedAt": datetime.now().isoformat(),
                "sessionId": item.get("claudeSessionId") or item.get("sessionId"),
                "source": item.get("source"),
                "openclawSessionId": item.get("openclawSessionId"),
                "openclawMessageId": item.get("openclawMessageId"),
                "senderLabel": item.get("senderLabel"),
                "prompt": item.get("prompt"),
                "preparedPrompt": "",
                "model": "",
                "ok": False,
                "runState": "BLOCKED",
                "turnCount": 0,
                "turns": [],
                "result": "",
                "stderr": str(exc),
            }

        with OPENCLAW_DISPATCH_LOCK:
            OPENCLAW_DISPATCH_ACTIVE.pop(route_key, None)
            if result.get("sessionId") and route_key:
                OPENCLAW_ROUTE_BINDINGS[route_key] = str(result.get("sessionId") or "")
            _append_dispatch_history_locked(
                {
                    "dispatchId": result.get("dispatchId"),
                    "routeKey": route_key,
                    "finishedAt": result.get("finishedAt"),
                    "sessionId": result.get("sessionId"),
                    "source": result.get("source"),
                    "preview": _dispatch_preview(result.get("prompt") or ""),
                    "ok": bool(result.get("ok")),
                    "runState": result.get("runState"),
                    "turnCount": result.get("turnCount"),
                    "logPath": result.get("logPath"),
                    "stderr": _dispatch_preview(result.get("stderr") or "", 120),
                }
            )
            _save_dispatch_state_locked()


def _ensure_openclaw_dispatch_workers() -> None:
    if not CLAUDE_CONSOLE_ENABLE_OPENCLAW:
        return
    with OPENCLAW_DISPATCH_LOCK:
        route_keys = []
        for item in OPENCLAW_DISPATCH_QUEUE:
            route_key = str(item.get("routeKey") or item.get("dispatchId") or "").strip()
            if route_key and route_key not in route_keys:
                route_keys.append(route_key)
        for route_key in route_keys:
            worker = OPENCLAW_DISPATCH_WORKERS.get(route_key)
            if worker and worker.is_alive():
                continue
            worker = threading.Thread(
                target=_openclaw_dispatch_worker,
                args=(route_key,),
                name=f"openclaw-dispatch-{route_key[:10]}",
                daemon=True,
            )
            OPENCLAW_DISPATCH_WORKERS[route_key] = worker
            worker.start()


def _parse_toml_value(raw_value: str):
    value = raw_value.strip()
    if not value:
        return ""
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    if value.startswith(("'", '"')):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, str) else str(parsed)
        except Exception:
            return value.strip("'\"")
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except Exception:
            return value
    if re.fullmatch(r"-?\d+\.\d+", value):
        try:
            return float(value)
        except Exception:
            return value
    return value


def _describe_rrule(rrule: str) -> str:
    value = str(rrule or "").strip().upper()
    if not value:
        return "未设置计划"
    hour_match = re.search(r"BYHOUR=(\d{1,2})", value)
    minute_match = re.search(r"BYMINUTE=(\d{1,2})", value)
    clock = f"{int(hour_match.group(1)) if hour_match else 0:02d}:{int(minute_match.group(1)) if minute_match else 0:02d}"
    if "FREQ=WEEKLY" in value:
        day_map = {
            "MO": "周一",
            "TU": "周二",
            "WE": "周三",
            "TH": "周四",
            "FR": "周五",
            "SA": "周六",
            "SU": "周日",
        }
        raw_days = re.search(r"BYDAY=([A-Z,]+)", value)
        days = [day_map.get(day.strip(), day.strip()) for day in (raw_days.group(1).split(",") if raw_days else []) if day.strip()]
        day_text = "、".join(days) if days else "每周"
        return f"{day_text} {clock}"
    if "FREQ=HOURLY" in value:
        interval_match = re.search(r"INTERVAL=(\d+)", value)
        interval = int(interval_match.group(1)) if interval_match else 1
        return f"每 {interval} 小时一次"
    return "自定义计划"


def _read_automations() -> list[dict]:
    root = Path(CODEX_AUTOMATIONS_DIR)
    items: list[dict] = []
    if root.exists():
        for path in sorted(root.glob("*/automation.toml")):
            record: dict = {}
            try:
                for raw_line in path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, raw_value = line.split("=", 1)
                    record[key.strip()] = _parse_toml_value(raw_value)
            except Exception:
                continue
            items.append(
                {
                    "id": str(record.get("id") or path.parent.name),
                    "name": str(record.get("name") or path.parent.name),
                    "status": str(record.get("status") or "UNKNOWN"),
                    "schedule": _describe_rrule(str(record.get("rrule") or "")),
                    "promptPreview": str(record.get("prompt") or "").strip(),
                    "path": str(path),
                    "cwds": [str(item) for item in (record.get("cwds") or []) if str(item).strip()],
                    "updatedAt": record.get("updated_at") or record.get("created_at") or 0,
                    "source": "Codex Automation",
                    "sourceKind": "codex-automation",
                    "deleteKind": "codex-automation",
                    "canDelete": True,
                }
            )
    jobs_blob = _read_json_file(OPENCLAW_JOBS_FILE, {}) if CLAUDE_CONSOLE_ENABLE_OPENCLAW and OPENCLAW_JOBS_FILE else {}
    jobs = jobs_blob.get("jobs") if isinstance(jobs_blob, dict) else []
    if CLAUDE_CONSOLE_ENABLE_OPENCLAW and isinstance(jobs, list):
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "").strip()
            if not job_id:
                continue
            payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
            schedule = job.get("schedule") if isinstance(job.get("schedule"), dict) else {}
            state = job.get("state") if isinstance(job.get("state"), dict) else {}
            expr = str(schedule.get("expr") or "").strip()
            tz = str(schedule.get("tz") or "").strip()
            schedule_label = f"Cron · {expr}" if expr else "Cron"
            if tz:
                schedule_label = f"{schedule_label} · {tz}"
            status_parts = ["启用" if bool(job.get("enabled", True)) else "停用"]
            last_status = str(state.get("lastStatus") or state.get("lastRunStatus") or "").strip()
            if last_status:
                status_parts.append(last_status)
            items.append(
                {
                    "id": job_id,
                    "name": str(job.get("name") or job_id),
                    "status": " / ".join(status_parts),
                    "schedule": schedule_label,
                    "promptPreview": str(payload.get("message") or "").strip(),
                    "path": OPENCLAW_JOBS_FILE,
                    "cwds": [],
                    "updatedAt": int(job.get("updatedAtMs") or job.get("createdAtMs") or 0),
                    "source": "External Scheduler",
                    "sourceKind": "openclaw-cron",
                    "deleteKind": "openclaw-cron",
                    "canDelete": True,
                    "agentId": str(job.get("agentId") or ""),
                    "enabled": bool(job.get("enabled", True)),
                    "cronExpr": expr,
                    "lastRunStatus": last_status,
                }
            )
    items.sort(key=lambda item: (0 if item.get("sourceKind") == "openclaw-cron" else 1, -int(item.get("updatedAt") or 0), str(item.get("name") or "").lower()))
    return items


def _parse_skill_front_matter(path: Path) -> dict:
    name = path.parent.name
    description = ""
    front_matter: dict[str, object] = {"name": name, "description": description}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return front_matter
    if lines and lines[0].strip() == "---":
        for line in lines[1:20]:
            stripped = line.strip()
            if stripped == "---":
                break
            if ":" not in stripped:
                continue
            key, raw_value = stripped.split(":", 1)
            key = key.strip()
            value = raw_value.strip().strip('"').strip("'")
            front_matter[key] = value
    front_matter["name"] = str(front_matter.get("name") or name)
    front_matter["description"] = str(front_matter.get("description") or description)
    return front_matter


def _read_local_skills() -> list[dict]:
    items_by_id: dict[str, dict] = {}
    for root_dir in CLAUDE_LOCAL_SKILL_DIRS:
        root = Path(root_dir)
        if not root.exists():
            continue
        for path in sorted(root.rglob("SKILL.md")):
            meta = _parse_skill_front_matter(path)
            skill_id = str(meta.get("name") or path.parent.name)
            items_by_id[skill_id] = {
                "id": skill_id,
                "name": str(meta.get("name") or path.parent.name),
                "description": str(meta.get("description") or "本地技能说明"),
                "path": str(path),
                "source": "本地技能",
                "plugin": "",
            }
    return sorted(items_by_id.values(), key=lambda item: str(item.get("name") or "").lower())


def _read_plugin_skills() -> list[dict]:
    installed = _read_json_file(CLAUDE_PLUGIN_INSTALLED_FILE, {})
    plugins = installed.get("plugins") if isinstance(installed, dict) else {}
    if not isinstance(plugins, dict):
        return []
    items_by_id: dict[str, dict] = {}
    for plugin_key, installs in plugins.items():
        plugin_name = str(plugin_key).split("@", 1)[0]
        if not isinstance(installs, list):
            continue
        for install in installs:
            if not isinstance(install, dict):
                continue
            install_path = Path(str(install.get("installPath") or "")).expanduser()
            marketplace_file = install_path / ".claude-plugin" / "marketplace.json"
            marketplace = _read_json_file(str(marketplace_file), {})
            plugin_entries = marketplace.get("plugins") if isinstance(marketplace, dict) else []
            if not isinstance(plugin_entries, list):
                continue
            plugin_entry = next(
                (entry for entry in plugin_entries if isinstance(entry, dict) and str(entry.get("name") or "") == plugin_name),
                None,
            )
            if not isinstance(plugin_entry, dict):
                continue
            for skill_ref in plugin_entry.get("skills") or []:
                skill_dir = (install_path / str(skill_ref)).resolve()
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                meta = _parse_skill_front_matter(skill_file)
                skill_id = str(meta.get("name") or skill_dir.name)
                current = items_by_id.get(skill_id)
                if current is None:
                    current = {
                        "id": skill_id,
                        "name": str(meta.get("name") or skill_dir.name),
                        "description": str(meta.get("description") or "Claude Plugin 技能"),
                        "path": str(skill_file),
                        "source": "Claude 插件",
                        "plugin": plugin_key,
                        "plugins": [],
                    }
                    items_by_id[skill_id] = current
                current.setdefault("plugins", [])
                if plugin_key not in current["plugins"]:
                    current["plugins"].append(plugin_key)
    values = list(items_by_id.values())
    for item in values:
        plugins_list = item.get("plugins") or []
        item["plugin"] = " / ".join(sorted(str(entry) for entry in plugins_list))
    return sorted(values, key=lambda item: str(item.get("name") or "").lower())


def _read_skills() -> list[dict]:
    items_by_id: dict[str, dict] = {}
    for item in _read_plugin_skills() + _read_local_skills():
        items_by_id[str(item.get("id") or uuid.uuid4().hex)] = item
    return sorted(items_by_id.values(), key=lambda item: str(item.get("name") or "").lower())


def _read_agents() -> list[dict]:
    items_by_id: dict[str, dict] = {}
    for root_dir in CLAUDE_AGENT_DIRS:
        root = Path(root_dir)
        if not root.exists():
            continue
        for path in sorted(root.glob("*.md")):
            meta = _parse_skill_front_matter(path)
            agent_name = str(meta.get("name") or path.stem)
            items_by_id[agent_name] = {
                "id": agent_name,
                "name": agent_name,
                "description": str(meta.get("description") or "Claude 自定义 agent"),
                "path": str(path),
                "source": "用户 Agent" if str(root).startswith(str(Path(CLAUDE_HOME_DIR))) else "项目 Agent",
                "model": str(meta.get("model") or "inherit"),
            }
    return sorted(items_by_id.values(), key=lambda item: str(item.get("name") or "").lower())


def _read_mcp_servers() -> list[dict]:
    settings = _read_json_file(CLAUDE_USER_SETTINGS_FILE, {})
    server_map = settings.get("mcpServers") if isinstance(settings, dict) else {}
    if not isinstance(server_map, dict):
        return []
    claude_cli_available, claude_real_bin = _resolve_real_claude_bin()
    if claude_cli_available:
        status_result = _run_capture([CLAUDE_WRAPPER_PATH, "mcp", "list"], cwd=CLAUDE_WORKSPACE_ROOT, timeout=20)
    else:
        status_result = {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"Claude CLI not found: {claude_real_bin or 'claude'}",
        }
    status_map: dict[str, str] = {}
    output_text = "\n".join(
        [
            str(status_result.get("stdout") or ""),
            str(status_result.get("stderr") or ""),
        ]
    )
    for raw_line in output_text.splitlines():
        line = raw_line.strip()
        if ":" not in line or " - " not in line:
            continue
        name = line.split(":", 1)[0].strip()
        if "✓ Connected" in line:
            status_map[name] = "connected"
        elif "✗ Failed to connect" in line:
            status_map[name] = "failed"
    items: list[dict] = []
    for name, config in sorted(server_map.items()):
        if not isinstance(config, dict):
            continue
        args = config.get("args") or []
        command = str(config.get("command") or "")
        items.append(
            {
                "id": name,
                "name": name,
                "description": " ".join([command, *[str(arg) for arg in args]]).strip(),
                "path": CLAUDE_USER_SETTINGS_FILE,
                "source": "Claude MCP",
                "transport": str(config.get("type") or "stdio"),
                "status": status_map.get(name, "unknown"),
                "command": command,
            }
        )
    return items


def _library_cache_signature() -> tuple:
    watch_paths = [
        CODEX_AUTOMATIONS_DIR,
        CLAUDE_USER_SETTINGS_FILE,
        CLAUDE_PLUGIN_INSTALLED_FILE,
        *CLAUDE_LOCAL_SKILL_DIRS,
        *CLAUDE_AGENT_DIRS,
    ]
    signature: list[tuple[str, float, int]] = []
    for raw_path in watch_paths:
        path = Path(str(raw_path))
        try:
            stat = path.stat()
            signature.append((str(path), float(stat.st_mtime), int(stat.st_size)))
        except FileNotFoundError:
            signature.append((str(path), -1.0, 0))
    return tuple(signature)


def _clear_library_cache() -> None:
    with LIBRARY_CACHE_LOCK:
        LIBRARY_CACHE["signature"] = None
        LIBRARY_CACHE["payload"] = None
        LIBRARY_CACHE["createdAt"] = 0.0


def _build_library(force_refresh: bool = False) -> dict:
    signature = _library_cache_signature()
    now = time.time()
    with LIBRARY_CACHE_LOCK:
        cached_signature = LIBRARY_CACHE.get("signature")
        cached_payload = LIBRARY_CACHE.get("payload")
        cached_created_at = float(LIBRARY_CACHE.get("createdAt") or 0.0)
        if (
            not force_refresh
            and isinstance(cached_payload, dict)
            and cached_signature == signature
            and (now - cached_created_at) <= CLAUDE_LIBRARY_CACHE_TTL_SECONDS
        ):
            return copy.deepcopy(cached_payload)

    automations = _read_automations()
    skills = _read_skills()
    agents = _read_agents()
    mcps = _read_mcp_servers()
    payload = {
        "automations": automations,
        "skills": skills,
        "agents": agents,
        "mcps": mcps,
        "counts": {
            "automations": len(automations),
            "skills": len(skills),
            "agents": len(agents),
            "mcps": len(mcps),
        },
    }
    with LIBRARY_CACHE_LOCK:
        LIBRARY_CACHE["signature"] = signature
        LIBRARY_CACHE["payload"] = copy.deepcopy(payload)
        LIBRARY_CACHE["createdAt"] = now
    return payload


def _compose_prompt_with_attachments(prompt: str, attachments: list[dict] | None) -> str:
    items = [item for item in (attachments or []) if isinstance(item, dict) and str(item.get("path") or "").strip()]
    if not items:
        return prompt
    header_lines = ["已附文件，请优先直接读取这些本地路径："]
    for item in items:
        name = str(item.get("name") or Path(str(item.get("path") or "")).name)
        header_lines.append(f"- {name}: {str(item.get('path') or '').strip()}")
    header_lines.append("")
    header_lines.append(prompt.strip())
    return "\n".join(header_lines).strip()


def _path_within_roots(candidate: str, roots: list[str]) -> str | None:
    real_candidate = os.path.realpath(os.path.expanduser(candidate))
    for root in roots:
        real_root = os.path.realpath(os.path.expanduser(root))
        if real_candidate == real_root or real_candidate.startswith(real_root + os.sep):
            return real_candidate
    return None


def _build_status(force_refresh: bool = False) -> dict:
    now = time.time()
    with STATUS_CACHE_LOCK:
        cached_payload = STATUS_CACHE.get("payload")
        cached_created_at = float(STATUS_CACHE.get("createdAt") or 0.0)
        if (
            not force_refresh
            and isinstance(cached_payload, dict)
            and (now - cached_created_at) <= CLAUDE_STATUS_CACHE_TTL_SECONDS
        ):
            return copy.deepcopy(cached_payload)

    claude_cli_available, claude_real_bin = _resolve_real_claude_bin()
    if claude_cli_available:
        claude_version = _run_capture([CLAUDE_WRAPPER_PATH, "--version"], cwd=CLAUDE_WORKSPACE_ROOT, timeout=10)
    else:
        claude_version = {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"Claude CLI not found: {claude_real_bin or 'claude'}",
        }
    router_config = _read_json_file(CLAUDE_ROUTER_CONFIG_FILE, {})
    providers = []
    for provider in _router_provider_entries(router_config):
        providers.append(
            {
                "name": provider.get("name") or "",
                "models": provider.get("models") or [],
                "apiBaseUrl": provider.get("api_base_url") or "",
            }
        )
    router_section = _router_section(router_config)
    payload = {
        "ok": True,
        "generatedAt": datetime.now().isoformat(),
        "claude": {
            "binary": CLAUDE_WRAPPER_PATH,
            "realBinary": claude_real_bin,
            "workspaceRoot": CLAUDE_WORKSPACE_ROOT,
            "exists": os.path.exists(CLAUDE_WRAPPER_PATH),
            "realBinaryAvailable": claude_cli_available,
            "version": claude_version.get("stdout") or claude_version.get("stderr") or "",
            "versionOk": bool(claude_version.get("ok")),
        },
        "runtime": {
            "sourceRoot": SOURCE_ROOT,
            "runtimeRoot": CLAUDE_CONSOLE_RUNTIME_ROOT,
            "uploadRoot": CLAUDE_CONSOLE_UPLOAD_ROOT,
        },
        "health": {
            "router": _probe_json(CLAUDE_ROUTER_HEALTH_URL, timeout=2.0),
            "proxy": _probe_json(CLAUDE_PROXY_HEALTH_URL, timeout=2.0),
        },
        "routerConfig": {
            "path": CLAUDE_ROUTER_CONFIG_FILE,
            "customRouterPath": router_config.get("CUSTOM_ROUTER_PATH") or CLAUDE_ROUTER_CUSTOM_FILE,
            "default": router_section.get("default"),
            "background": router_section.get("background"),
            "think": router_section.get("think"),
            "longContext": router_section.get("longContext"),
            "longContextThreshold": router_section.get("longContextThreshold"),
            "image": router_section.get("image"),
            "providers": providers,
        },
        "assignments": CLAUDE_ASSIGNMENT_MATRIX,
        "sessionStore": {
            "projectDir": CLAUDE_PROJECT_SESSIONS_DIR,
            "metaFile": CLAUDE_CHAT_META_FILE,
            "openclawOpsSessionId": _resolve_openclaw_fixed_session_id() if CLAUDE_CONSOLE_ENABLE_OPENCLAW else "",
        },
        "openclawDispatch": _dispatch_state_snapshot_locked(),
        "modes": [
            {
                "id": mode,
                "label": info["label"],
                "model": info["model"],
                "tag": info["tag"],
                "description": info["description"],
                "effort": info["effort"],
            }
            for mode, info in CLAUDE_MODE_CONFIG.items()
        ],
        "agentModes": [
            {
                "id": agent_mode,
                "label": info["label"],
                "agent": info["agent"],
                "description": info["description"],
            }
            for agent_mode, info in CLAUDE_AGENT_MODE_CONFIG.items()
        ],
        "commands": {
            "interactive": "claude",
            "continueLatest": "claude -c",
            "quickRun": "claude -p",
        },
        "webDefaults": {
            "permissionMode": CLAUDE_WEB_PERMISSION_MODE,
            "chatTimeoutSeconds": CLAUDE_CHAT_TIMEOUT_SECONDS,
            "locale": _load_editable_settings().get("CLAUDE_CONSOLE_LOCALE") or EDITABLE_SETTINGS_DEFAULTS["CLAUDE_CONSOLE_LOCALE"],
        },
        "tmux": _tmux_state(),
        "activeRuns": _combined_active_runs(),
        "logs": {
            "routerWrapper": _read_tail(CLAUDE_ROUTER_WRAPPER_LOG),
            "routerErrors": _read_tail(CLAUDE_ROUTER_ERR_LOG),
            "proxyLog": _read_tail(CLAUDE_PROXY_LOG),
            "proxyErrors": _read_tail(CLAUDE_PROXY_ERR_LOG),
        },
        "installers": {
            "everythingClaudeCode": _everything_claude_code_status(),
        },
    }
    with STATUS_CACHE_LOCK:
        STATUS_CACHE["payload"] = copy.deepcopy(payload)
        STATUS_CACHE["createdAt"] = now
    return payload


def _build_bootstrap(include_archived: bool = False) -> dict:
    _claude_cleanup_empty_sessions(
        CLAUDE_PROJECT_SESSIONS_DIR,
        CLAUDE_CHAT_META_FILE,
        trash_root=OPENCLAW_SESSION_TRASH_ROOT,
    )
    payload = _build_status()
    payload["library"] = _build_library()
    payload["sessions"] = _claude_list_sessions(
        CLAUDE_PROJECT_SESSIONS_DIR,
        CLAUDE_CHAT_META_FILE,
        include_archived=include_archived,
        limit=160,
    )
    payload["folders"] = _claude_list_folder_registry(CLAUDE_CHAT_META_FILE, payload["sessions"])
    payload["sessionCount"] = len(payload["sessions"])
    return _json_safe(payload)


def _build_poll(include_archived: bool = False) -> dict:
    _claude_cleanup_empty_sessions(
        CLAUDE_PROJECT_SESSIONS_DIR,
        CLAUDE_CHAT_META_FILE,
        trash_root=OPENCLAW_SESSION_TRASH_ROOT,
    )
    sessions = _claude_list_sessions(
        CLAUDE_PROJECT_SESSIONS_DIR,
        CLAUDE_CHAT_META_FILE,
        include_archived=include_archived,
        limit=200,
    )
    return _json_safe(
        {
            "ok": True,
            "generatedAt": datetime.now().isoformat(),
            "sessions": sessions,
            "sessionCount": len(sessions),
            "openclawDispatch": _dispatch_state_snapshot_locked(),
            "activeRuns": _combined_active_runs(),
            "sessionStore": {
                "openclawOpsSessionId": _resolve_openclaw_fixed_session_id() if CLAUDE_CONSOLE_ENABLE_OPENCLAW else "",
            },
            "tmux": _tmux_state(),
        }
    )


def _delete_codex_automation(automation_id: str):
    automation_dir = Path(CODEX_AUTOMATIONS_DIR) / automation_id
    if not automation_dir.exists():
        return jsonify({"ok": False, "msg": "自动化不存在"}), 404
    trash_root = Path.home() / ".Trash" / "claude-console-automations"
    trash_root.mkdir(parents=True, exist_ok=True)
    target = trash_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{automation_id}"
    shutil.move(str(automation_dir), str(target))
    _clear_library_cache()
    return jsonify({"ok": True, "id": automation_id, "sourceKind": "codex-automation", "movedTo": str(target)})


def _delete_openclaw_cron_job(job_id: str):
    if not CLAUDE_CONSOLE_ENABLE_OPENCLAW or not OPENCLAW_JOBS_FILE:
        return jsonify({"ok": False, "msg": "外部调度集成未启用"}), 404
    jobs_blob = _read_json_file(OPENCLAW_JOBS_FILE, {})
    jobs = jobs_blob.get("jobs") if isinstance(jobs_blob, dict) else []
    job = next(
        (item for item in jobs if isinstance(item, dict) and str(item.get("id") or "").strip() == job_id),
        None,
    )
    if not isinstance(job, dict):
        return jsonify({"ok": False, "msg": "外部调度任务不存在"}), 404

    trash_root = Path(OPENCLAW_AUTOMATION_TRASH_ROOT)
    trash_root.mkdir(parents=True, exist_ok=True)
    snapshot_path = trash_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{job_id}.json"
    snapshot_path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [OPENCLAW_BIN, "cron", "rm", job_id],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        return (
            jsonify(
                {
                    "ok": False,
                    "msg": result.stderr.strip() or result.stdout.strip() or "删除外部调度任务失败",
                }
            ),
            500,
        )
    _clear_library_cache()
    return jsonify(
        {
            "ok": True,
            "id": job_id,
            "sourceKind": "openclaw-cron",
            "jobName": str(job.get("name") or job_id),
            "snapshotPath": str(snapshot_path),
        }
    )


def _write_terminal_script(
    mode: str,
    prompt: str,
    continue_latest: bool,
    session_id: str = "",
    agent_mode: str = "auto",
    permission_mode: str = CLAUDE_WEB_PERMISSION_MODE,
) -> str:
    if IS_WINDOWS:
        fd, script_path = tempfile.mkstemp(prefix="claude-console-", suffix=".ps1")
        os.close(fd)
        normalized_agent_mode = _normalize_agent_mode(agent_mode)
        agent_name = _resolve_agent_name(normalized_agent_mode, prompt, mode)
        prepared_prompt = _prepare_claude_prompt(prompt, mode, normalized_agent_mode)
        command_parts = [f'& "{CLAUDE_WRAPPER_PATH}"']
        if agent_name:
            command_parts.extend(["--agent", shlex.quote(agent_name)])
        if permission_mode == "bypassPermissions":
            command_parts.append("--dangerously-skip-permissions")
        if permission_mode:
            command_parts.extend(["--permission-mode", shlex.quote(permission_mode)])
        for path in _claude_allowed_dirs():
            if os.path.realpath(path) != os.path.realpath(CLAUDE_WORKSPACE_ROOT):
                command_parts.append(f"--add-dir={shlex.quote(path)}")
        if session_id:
            command_parts.extend(["-r", shlex.quote(session_id)])
        elif continue_latest:
            command_parts.append("-c")
        elif prepared_prompt:
            command_parts.append("$promptText")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("$ErrorActionPreference = 'Stop'\n")
            f.write(f"Set-Location -Path {json.dumps(CLAUDE_WORKSPACE_ROOT)}\n")
            f.write("$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'\n")
            f.write("$env:NO_PROXY = '127.0.0.1,localhost'\n")
            f.write("$env:no_proxy = '127.0.0.1,localhost'\n")
            for key in PROXY_ENV_KEYS:
                f.write(f"Remove-Item Env:{key} -ErrorAction SilentlyContinue\n")
            if prepared_prompt and not session_id and not continue_latest:
                f.write(f"$promptText = @'\n{prepared_prompt}\n'@\n")
            f.write("Write-Host 'Claude Console 已启动'\n")
            f.write("Write-Host ''\n")
            f.write("try {\n")
            f.write(f"  {' '.join(command_parts)}\n")
            f.write("} catch {\n")
            f.write("  Write-Host ''\n")
            f.write("  Write-Host ('Claude 退出: ' + $_.Exception.Message)\n")
            f.write("}\n")
            f.write("Read-Host '按 Enter 关闭窗口'\n")
        return script_path

    fd, script_path = tempfile.mkstemp(prefix="claude-console-", suffix=".command")
    normalized_agent_mode = _normalize_agent_mode(agent_mode)
    agent_name = _resolve_agent_name(normalized_agent_mode, prompt, mode)
    prepared_prompt = _prepare_claude_prompt(prompt, mode, normalized_agent_mode)
    tmux_binary = _tmux_binary()
    terminal_print_mode = bool(prepared_prompt and not session_id and not continue_latest)
    inject_prompt_via_tmux = bool(tmux_binary and prepared_prompt and not terminal_print_mode and not session_id and not continue_latest)
    command_parts = [shlex.quote(CLAUDE_WRAPPER_PATH)]
    if terminal_print_mode:
        command_parts.append("-p")
    if agent_name:
        command_parts.extend(["--agent", shlex.quote(agent_name)])
    if permission_mode == "bypassPermissions":
        command_parts.append("--dangerously-skip-permissions")
    if permission_mode:
        command_parts.extend(["--permission-mode", shlex.quote(permission_mode)])
    command_parts.extend(
        f"--add-dir={shlex.quote(path)}"
        for path in _claude_allowed_dirs()
        if os.path.realpath(path) != os.path.realpath(CLAUDE_WORKSPACE_ROOT)
    )
    if session_id:
        command_parts.extend(["-r", shlex.quote(session_id)])
    elif continue_latest:
        command_parts.append("-c")
    elif prepared_prompt and not inject_prompt_via_tmux:
        command_parts.append('"$PROMPT"')
    claude_command = " ".join(part for part in command_parts if part).strip()
    tmux_session_name = _tmux_session_name(session_id=session_id, prompt=prompt, continue_latest=continue_latest)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("#!/bin/zsh\n")
        f.write("set -euo pipefail\n")
        f.write(f"export PATH={shlex.quote(str(Path.home() / '.local' / 'bin'))}:$PATH\n")
        f.write("unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy\n")
        f.write("export NO_PROXY=127.0.0.1,localhost\n")
        f.write("export no_proxy=127.0.0.1,localhost\n")
        f.write(f"cd {shlex.quote(CLAUDE_WORKSPACE_ROOT)}\n")
        f.write("export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1\n")
        f.write(f"TMUX_SESSION={shlex.quote(tmux_session_name)}\n")
        f.write("TMUX_RUN_PANE=\"${TMUX_SESSION}:0.0\"\n")
        f.write("RUN_SCRIPT=\"${TMPDIR:-/tmp}/${TMUX_SESSION}-claude-run.sh\"\n")
        f.write("PROMPT_FILE=\"${TMPDIR:-/tmp}/${TMUX_SESSION}-claude-prompt.txt\"\n")
        f.write("cat > \"$RUN_SCRIPT\" <<'__CLAUDE_RUN__'\n")
        f.write("#!/bin/zsh\n")
        f.write("set -euo pipefail\n")
        f.write(f"export PATH={shlex.quote(str(Path.home() / '.local' / 'bin'))}:$PATH\n")
        f.write("unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy\n")
        f.write("export NO_PROXY=127.0.0.1,localhost\n")
        f.write("export no_proxy=127.0.0.1,localhost\n")
        f.write(f"cd {shlex.quote(CLAUDE_WORKSPACE_ROOT)}\n")
        f.write("export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1\n")
        f.write("clear\n")
        f.write("printf '\\033]0;Claude Console\\007'\n")
        f.write("echo 'Claude Console 已启动'\n")
        f.write(f"echo '工作区: {CLAUDE_WORKSPACE_ROOT}'\n")
        f.write("echo ''\n")
        if prepared_prompt and not inject_prompt_via_tmux:
            f.write("PROMPT=$(cat <<'__CLAUDE_PROMPT__'\n")
            f.write(prepared_prompt)
            f.write("\n__CLAUDE_PROMPT__\n)\n")
        f.write("CLAUDE_EXIT=0\n")
        f.write(claude_command + " || CLAUDE_EXIT=$?\n")
        f.write("if [[ \"$CLAUDE_EXIT\" != \"0\" ]]; then\n")
        f.write("  echo ''\n")
        f.write("  echo \"Claude 退出码: $CLAUDE_EXIT\"\n")
        f.write("fi\n")
        f.write("exec /bin/zsh\n")
        f.write("__CLAUDE_RUN__\n")
        f.write("chmod +x \"$RUN_SCRIPT\"\n")
        if tmux_binary:
            f.write(f"TMUX_BIN={shlex.quote(tmux_binary)}\n")
            if inject_prompt_via_tmux:
                f.write("cat > \"$PROMPT_FILE\" <<'__CLAUDE_PROMPT_FILE__'\n")
                f.write(prepared_prompt)
                f.write("\n__CLAUDE_PROMPT_FILE__\n")
            f.write("MONITOR_SCRIPT=\"${TMPDIR:-/tmp}/${TMUX_SESSION}-claude-monitor.sh\"\n")
            f.write("cat > \"$MONITOR_SCRIPT\" <<'__CLAUDE_MONITOR__'\n")
            f.write("#!/bin/zsh\n")
            f.write("set -euo pipefail\n")
            f.write("while true; do\n")
            f.write("  clear\n")
            f.write("  echo 'Claude Code tmux 监控面板'\n")
            f.write("  date '+%Y-%m-%d %H:%M:%S'\n")
            f.write("  echo ''\n")
            f.write("  /usr/bin/curl -fsS 'http://127.0.0.1:18882/claude-console/poll?includeArchived=1' | /usr/bin/python3 -c 'import json,sys; data=json.load(sys.stdin); runs=data.get(\"activeRuns\") or []; print(\"active runs:\", len(runs)); [print(\"-\", (item.get(\"agentName\") or item.get(\"runId\") or \"run\"), item.get(\"sessionId\") or \"\", item.get(\"routeKey\") or \"\") for item in runs[:8]]; dispatch=data.get(\"openclawDispatch\") or {}; print(\"dispatch queue:\", dispatch.get(\"queueLength\") or 0); tmux=data.get(\"tmux\") or {}; print(\"tmux sessions:\", tmux.get(\"sessionCount\") or 0); [print(\"  ·\", item.get(\"name\") or \"session\", \"w=\", item.get(\"windows\") or 0, \"attached=\", item.get(\"attached\") or 0) for item in (tmux.get(\"sessions\") or [])[:6]]' 2>/dev/null || echo 'poll unavailable'\n")
            f.write("  echo ''\n")
            f.write("  echo '[router tail]'\n")
            f.write("  tail -n 18 \"$HOME/Library/Logs/claude-code-router-wrapper.log\" 2>/dev/null || true\n")
            f.write("  echo ''\n")
            f.write("  echo '[proxy tail]'\n")
            f.write("  tail -n 18 \"$HOME/Library/Logs/claude-code-dashscope-proxy.log\" 2>/dev/null || true\n")
            f.write("  sleep 1.5\n")
            f.write("done\n")
            f.write("__CLAUDE_MONITOR__\n")
            f.write("chmod +x \"$MONITOR_SCRIPT\"\n")
            f.write("auto_accept_claude_onboarding() {\n")
            f.write("  local attempt pane_text\n")
            f.write("  for attempt in {1..24}; do\n")
            f.write("    pane_text=\"$($TMUX_BIN capture-pane -pt \"$TMUX_RUN_PANE\" -S -120 2>/dev/null || true)\"\n")
            f.write("    if [[ -z \"$pane_text\" ]]; then\n")
            f.write("      /bin/sleep 0.5\n")
            f.write("      continue\n")
            f.write("    fi\n")
            f.write("    if print -r -- \"$pane_text\" | /usr/bin/grep -Fq 'Choose the text style'; then\n")
            f.write("      \"$TMUX_BIN\" send-keys -t \"$TMUX_RUN_PANE\" Enter >/dev/null 2>&1 || true\n")
            f.write("      /bin/sleep 0.8\n")
            f.write("      continue\n")
            f.write("    fi\n")
            f.write("    if print -r -- \"$pane_text\" | /usr/bin/grep -Eq 'Press Enter to continue|Security notes:'; then\n")
            f.write("      \"$TMUX_BIN\" send-keys -t \"$TMUX_RUN_PANE\" Enter >/dev/null 2>&1 || true\n")
            f.write("      /bin/sleep 0.8\n")
            f.write("      continue\n")
            f.write("    fi\n")
            f.write("    if print -r -- \"$pane_text\" | /usr/bin/grep -Eq 'Quick safety check|Yes, I trust this folder'; then\n")
            f.write("      \"$TMUX_BIN\" send-keys -t \"$TMUX_RUN_PANE\" Enter >/dev/null 2>&1 || true\n")
            f.write("      /bin/sleep 0.8\n")
            f.write("      continue\n")
            f.write("    fi\n")
            f.write("    if print -r -- \"$pane_text\" | /usr/bin/grep -Eq 'Bypass Permissions mode|Yes, I accept'; then\n")
            f.write("      \"$TMUX_BIN\" send-keys -t \"$TMUX_RUN_PANE\" Down Enter >/dev/null 2>&1 || true\n")
            f.write("      /bin/sleep 0.8\n")
            f.write("      continue\n")
            f.write("    fi\n")
            f.write("    if print -r -- \"$pane_text\" | /usr/bin/grep -Eq 'How can I help|> $|❯'; then\n")
            f.write("      break\n")
            f.write("    fi\n")
            f.write("    /bin/sleep 0.5\n")
            f.write("  done\n")
            f.write("}\n")
            f.write("inject_prompt_if_ready() {\n")
            f.write("  if [[ ! -s \"$PROMPT_FILE\" ]]; then\n")
            f.write("    return 0\n")
            f.write("  fi\n")
            f.write("  local attempt pane_text current_cmd buffer_name\n")
            f.write("  buffer_name=\"${TMUX_SESSION}-prompt\"\n")
            f.write("  for attempt in {1..40}; do\n")
            f.write("    pane_text=\"$($TMUX_BIN capture-pane -pt \"$TMUX_RUN_PANE\" -S -120 2>/dev/null || true)\"\n")
            f.write("    current_cmd=\"$($TMUX_BIN display-message -p -t \"$TMUX_RUN_PANE\" '#{pane_current_command}' 2>/dev/null || true)\"\n")
            f.write("    if print -r -- \"$pane_text\" | /usr/bin/grep -Eq 'Choose the text style|Press Enter to continue|Security notes:|Quick safety check|Yes, I trust this folder|Bypass Permissions mode|Yes, I accept'; then\n")
            f.write("      /bin/sleep 0.5\n")
            f.write("      continue\n")
            f.write("    fi\n")
            f.write("    if [[ \"$current_cmd\" == \"claude\" ]]; then\n")
            f.write("      \"$TMUX_BIN\" load-buffer -b \"$buffer_name\" \"$PROMPT_FILE\" >/dev/null 2>&1 || true\n")
            f.write("      \"$TMUX_BIN\" paste-buffer -b \"$buffer_name\" -t \"$TMUX_RUN_PANE\" >/dev/null 2>&1 || true\n")
            f.write("      \"$TMUX_BIN\" send-keys -t \"$TMUX_RUN_PANE\" Enter >/dev/null 2>&1 || true\n")
            f.write("      /bin/rm -f \"$PROMPT_FILE\" >/dev/null 2>&1 || true\n")
            f.write("      \"$TMUX_BIN\" delete-buffer -b \"$buffer_name\" >/dev/null 2>&1 || true\n")
            f.write("      break\n")
            f.write("    fi\n")
            f.write("    /bin/sleep 0.5\n")
            f.write("  done\n")
            f.write("}\n")
            f.write("if ! \"$TMUX_BIN\" has-session -t \"$TMUX_SESSION\" 2>/dev/null; then\n")
            f.write(f"  \"$TMUX_BIN\" new-session -d -s \"$TMUX_SESSION\" -c {shlex.quote(CLAUDE_WORKSPACE_ROOT)} \"$RUN_SCRIPT\"\n")
            f.write(f"  \"$TMUX_BIN\" split-window -h -t \"$TMUX_SESSION\":0 -c {shlex.quote(CLAUDE_WORKSPACE_ROOT)} \"$MONITOR_SCRIPT\"\n")
            f.write("  \"$TMUX_BIN\" set-option -t \"$TMUX_SESSION\" mouse on >/dev/null 2>&1 || true\n")
            f.write("  \"$TMUX_BIN\" select-layout -t \"$TMUX_SESSION\":0 even-horizontal >/dev/null 2>&1 || true\n")
            f.write("  auto_accept_claude_onboarding >/dev/null 2>&1 &\n")
            f.write("  inject_prompt_if_ready >/dev/null 2>&1 &\n")
            f.write("fi\n")
            f.write("exec \"$TMUX_BIN\" attach-session -t \"$TMUX_SESSION\"\n")
        else:
            f.write("exec \"$RUN_SCRIPT\"\n")
    os.chmod(script_path, 0o700)
    return script_path


def _open_terminal_script(script_path: str) -> dict:
    try:
        if IS_WINDOWS:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    f'Start-Process powershell -ArgumentList \'-NoProfile\',\'-ExecutionPolicy\',\'Bypass\',\'-File\',\'{script_path}\'',
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if result.returncode != 0:
                return {"ok": False, "scriptPath": script_path, "error": result.stderr.strip() or result.stdout.strip()}
            return {"ok": True, "scriptPath": script_path}
        result = subprocess.run(
            ["open", "-a", CLAUDE_TERMINAL_APP, script_path],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            return {"ok": False, "scriptPath": script_path, "error": result.stderr.strip() or result.stdout.strip()}
        return {"ok": True, "scriptPath": script_path}
    except Exception as exc:
        return {"ok": False, "scriptPath": script_path, "error": str(exc)}


def _serve_html(name: str):
    path = os.path.join(FRONTEND_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        html = f.read().replace("{{VERSION_TIMESTAMP}}", VERSION_TIMESTAMP)
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@app.after_request
def add_no_cache_headers(response):
    path = request.path or ""
    if path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.errorhandler(Exception)
def handle_runtime_exception(exc):
    if isinstance(exc, HTTPException):
        return exc
    _append_runtime_error_log(exc)
    if request.path.startswith("/claude-console"):
        return jsonify({"ok": False, "msg": "internal server error"}), 500
    return make_response("Internal Server Error", 500)


@app.route("/", methods=["GET"])
def index():
    return _serve_html("claude-console.html")


@app.route("/claude-console", methods=["GET"])
def claude_console_page():
    return _serve_html("claude-console.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "generatedAt": datetime.now().isoformat()})


def _is_startup_probe_request() -> bool:
    user_agent = str(request.headers.get("User-Agent") or "").lower()
    return "cfnetwork" in user_agent and "darwin" in user_agent and "applewebkit" not in user_agent


@app.route("/claude-console/status", methods=["GET"])
def claude_console_status():
    if request.args.get("full") != "1":
        return jsonify({"ok": True, "generatedAt": datetime.now().isoformat(), "ready": True})
    return jsonify(_build_status())


@app.route("/claude-console/bootstrap", methods=["GET"])
def claude_console_bootstrap():
    include_archived = (request.args.get("includeArchived", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
    if _is_startup_probe_request():
        return jsonify(
            {
                "ok": True,
                "generatedAt": datetime.now().isoformat(),
                "sessions": [],
                "sessionCount": 0,
                "folders": [],
            }
        )
    return jsonify(_build_bootstrap(include_archived=include_archived))


@app.route("/claude-console/poll", methods=["GET"])
def claude_console_poll():
    include_archived = (request.args.get("includeArchived", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
    return jsonify(_build_poll(include_archived=include_archived))


@app.route("/claude-console/sessions", methods=["GET"])
def claude_console_sessions():
    include_archived = (request.args.get("includeArchived", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
    return jsonify(
        {
            "ok": True,
            "items": _claude_list_sessions(
                CLAUDE_PROJECT_SESSIONS_DIR,
                CLAUDE_CHAT_META_FILE,
                include_archived=include_archived,
                limit=200,
            ),
        }
    )


@app.route("/claude-console/sessions/<session_id>", methods=["GET"])
def claude_console_session_detail(session_id: str):
    detail = _claude_get_session_detail(CLAUDE_PROJECT_SESSIONS_DIR, CLAUDE_CHAT_META_FILE, session_id)
    if detail is None:
        return jsonify({"ok": False, "msg": "session not found"}), 404
    summary = detail.get("summary") or {}
    if bool(summary.get("shellOnly")) or int(summary.get("messageCount") or 0) <= 0:
        return jsonify({"ok": False, "msg": "session not found"}), 404
    return jsonify({"ok": True, "session": detail["summary"], "messages": detail["messages"]})


@app.route("/claude-console/session-meta", methods=["POST"])
def claude_console_session_meta():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    session_id = str(data.get("sessionId") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "msg": "缺少 sessionId"}), 400
    meta = _claude_update_session_meta(
        CLAUDE_CHAT_META_FILE,
        session_id,
        title=None if "title" not in data else str(data.get("title") or ""),
        folder=None if "folder" not in data else str(data.get("folder") or ""),
        archived=None if "archived" not in data else bool(data.get("archived")),
        pinned=None if "pinned" not in data else bool(data.get("pinned")),
    )
    return jsonify({"ok": True, "sessionId": session_id, "meta": meta})


@app.route("/claude-console/folders", methods=["POST"])
def claude_console_create_folder():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    folder_name = str(data.get("name") or "").strip()
    if not folder_name:
        return jsonify({"ok": False, "msg": "缺少文件夹名称"}), 400
    try:
        folders = _claude_create_folder(CLAUDE_CHAT_META_FILE, folder_name)
    except ValueError:
        return jsonify({"ok": False, "msg": "缺少文件夹名称"}), 400
    return jsonify({"ok": True, "folders": folders})


@app.route("/claude-console/folders/rename", methods=["POST"])
def claude_console_rename_folder():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    old_name = str(data.get("oldName") or "").strip()
    new_name = str(data.get("newName") or "").strip()
    session_ids = data.get("sessionIds") or []
    if not isinstance(session_ids, list):
        session_ids = []
    try:
        payload = _claude_rename_folder(
            CLAUDE_CHAT_META_FILE,
            old_name,
            new_name,
            session_ids=[str(item or "").strip() for item in session_ids],
        )
    except ValueError:
        return jsonify({"ok": False, "msg": "缺少文件夹名称"}), 400
    return jsonify({"ok": True, **payload})


@app.route("/claude-console/openclaw-session/ensure", methods=["POST"])
def claude_console_ensure_openclaw_session():
    if not CLAUDE_CONSOLE_ENABLE_OPENCLAW:
        return jsonify({"ok": False, "msg": "外部调度集成未启用"}), 404
    data = request.get_json(silent=True) or {}
    force_reseed = bool(data.get("forceReseed")) if isinstance(data, dict) else False
    session_info = _ensure_openclaw_fixed_session(force_reseed=force_reseed)
    detail = _claude_get_session_detail(
        CLAUDE_PROJECT_SESSIONS_DIR,
        CLAUDE_CHAT_META_FILE,
        str(session_info.get("sessionId") or ""),
    )
    return jsonify(
        {
            "ok": True,
            "created": bool(session_info.get("created")),
            "sessionId": session_info.get("sessionId"),
            "session": detail["summary"] if detail else None,
            "seedReply": session_info.get("seedReply") or "",
        }
    )


@app.route("/claude-console/sessions/<session_id>", methods=["DELETE"])
def claude_console_delete_session(session_id: str):
    protected_session_id = _resolve_openclaw_fixed_session_id() if CLAUDE_CONSOLE_ENABLE_OPENCLAW else ""
    try:
        payload = _claude_delete_session(
            CLAUDE_PROJECT_SESSIONS_DIR,
            CLAUDE_CHAT_META_FILE,
            session_id,
            trash_root=OPENCLAW_SESSION_TRASH_ROOT,
            protected_session_ids={protected_session_id} if protected_session_id else set(),
        )
        return jsonify(payload)
    except PermissionError:
        return jsonify({"ok": False, "msg": "固定控制会话不允许删除"}), 409
    except FileNotFoundError:
        return jsonify({"ok": False, "msg": "会话不存在"}), 404
    except ValueError:
        return jsonify({"ok": False, "msg": "缺少有效 sessionId"}), 400


@app.route("/claude-console/upload", methods=["POST"])
def claude_console_upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "msg": "没有收到文件"}), 400
    upload_dir = Path(CLAUDE_CONSOLE_UPLOAD_ROOT) / datetime.now().strftime("%Y%m%d")
    upload_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for storage in files:
        original_name = str(getattr(storage, "filename", "") or "").strip()
        if not original_name:
            continue
        safe_name = _safe_filename(original_name)
        target = upload_dir / f"{datetime.now().strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}-{safe_name}"
        storage.save(str(target))
        items.append(
            {
                "name": Path(original_name).name,
                "path": str(target),
                "size": target.stat().st_size,
            }
        )
    if not items:
        return jsonify({"ok": False, "msg": "文件保存失败"}), 400
    return jsonify({"ok": True, "items": items})


@app.route("/claude-console/reveal", methods=["POST"])
def claude_console_reveal():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    candidate = str(data.get("path") or "").strip()
    if not candidate:
        return jsonify({"ok": False, "msg": "缺少 path"}), 400
    allowed_path = _path_within_roots(
        candidate,
        [
            SOURCE_ROOT,
            CLAUDE_CONSOLE_RUNTIME_ROOT,
            CLAUDE_WORKSPACE_ROOT,
            CODEX_HOME,
            EASY_CLAUDECODE_HOME,
        ],
    )
    if not allowed_path or not os.path.exists(allowed_path):
        return jsonify({"ok": False, "msg": "路径不允许或不存在"}), 400
    result = _open_local_path(allowed_path, reveal=True)
    if not result.get("ok"):
        return jsonify({"ok": False, "msg": result.get("msg") or "open failed"}), 500
    return jsonify({"ok": True, "path": allowed_path})


@app.route("/claude-console/openclaw-dispatch", methods=["POST"])
def claude_console_openclaw_dispatch():
    if not CLAUDE_CONSOLE_ENABLE_OPENCLAW:
        return jsonify({"ok": False, "msg": "外部调度集成未启用"}), 404
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "msg": "缺少 prompt"}), 400

    wait = bool(data.get("wait"))
    source = str(data.get("source") or "openclaw").strip() or "openclaw"
    openclaw_session_id = str(data.get("openclawSessionId") or "").strip()
    openclaw_message_id = str(data.get("openclawMessageId") or "").strip()
    sender_label = str(data.get("senderLabel") or "").strip()
    route_key = str(data.get("routeKey") or "").strip()
    claude_session_id = str(data.get("claudeSessionId") or "").strip()
    dispatch_item = {
        "dispatchId": uuid.uuid4().hex,
        "createdAt": datetime.now().isoformat(),
        "routeKey": route_key or "",
        "source": source,
        "sessionId": claude_session_id,
        "claudeSessionId": claude_session_id,
        "openclawSessionId": openclaw_session_id,
        "openclawMessageId": openclaw_message_id,
        "senderLabel": sender_label,
        "prompt": prompt,
        "preview": _dispatch_preview(prompt),
        "attempts": 0,
    }

    if wait:
        dispatch_item["startedAt"] = datetime.now().isoformat()
        try:
            result = _run_openclaw_dispatch_item(dispatch_item)
        except Exception as exc:  # noqa: BLE001
            result = {
                "dispatchId": dispatch_item["dispatchId"],
                "createdAt": dispatch_item["createdAt"],
                "startedAt": dispatch_item.get("startedAt"),
                "finishedAt": datetime.now().isoformat(),
                "sessionId": dispatch_item.get("sessionId"),
                "source": dispatch_item.get("source"),
                "preview": dispatch_item.get("preview"),
                "ok": False,
                "stderr": str(exc),
                "result": "",
            }
        with OPENCLAW_DISPATCH_LOCK:
            _append_dispatch_history_locked(
                {
                    "dispatchId": result.get("dispatchId"),
                    "finishedAt": result.get("finishedAt"),
                    "sessionId": result.get("sessionId"),
                    "source": result.get("source"),
                    "preview": dispatch_item.get("preview"),
                    "ok": bool(result.get("ok")),
                    "logPath": result.get("logPath"),
                    "stderr": _dispatch_preview(result.get("stderr") or "", 120),
                }
            )
            _save_dispatch_state_locked()
        status_code = 200 if result.get("ok") else 500
        return jsonify({"ok": bool(result.get("ok")), "queued": False, **result}), status_code

    with OPENCLAW_DISPATCH_LOCK:
        if route_key and not claude_session_id:
            bound_session = str(OPENCLAW_ROUTE_BINDINGS.get(route_key) or "").strip()
            bound_session = _resolve_openclaw_task_binding(route_key, bound_session)
            if bound_session:
                dispatch_item["sessionId"] = bound_session
                dispatch_item["claudeSessionId"] = bound_session
        OPENCLAW_DISPATCH_QUEUE.append(dispatch_item)
        queue_position = len(OPENCLAW_DISPATCH_QUEUE) + len(OPENCLAW_DISPATCH_ACTIVE)
        _save_dispatch_state_locked()
    _ensure_openclaw_dispatch_workers()
    return jsonify(
        {
            "ok": True,
            "queued": True,
            "queuePosition": queue_position,
            "dispatchId": dispatch_item["dispatchId"],
            "sessionId": dispatch_item["claudeSessionId"] or dispatch_item["sessionId"],
            "sessionTitle": _derive_openclaw_task_title(prompt, sender_label),
            "createdSession": False,
            "routeKey": route_key or dispatch_item["dispatchId"],
        }
    )


@app.route("/claude-console/automations/<automation_id>", methods=["DELETE"])
def claude_console_delete_automation(automation_id: str):
    safe_id = Path(str(automation_id or "")).name.strip()
    if not safe_id:
        return jsonify({"ok": False, "msg": "缺少自动化 ID"}), 400
    source_kind = str(request.args.get("source") or "codex-automation").strip().lower()
    if source_kind == "openclaw-cron":
        return _delete_openclaw_cron_job(safe_id)
    return _delete_codex_automation(safe_id)


@app.route("/claude-console/chat", methods=["POST"])
def claude_console_chat():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "msg": "请先输入消息"}), 400
    mode = _normalize_claude_mode(data.get("mode"))
    agent_mode = _normalize_agent_mode(data.get("agentMode"))
    session_id = str(data.get("sessionId") or "").strip() or None
    requested_session_id = session_id
    busy_session = _find_session_active_run(session_id) if session_id else None
    if busy_session:
        session_id = None
    permission_mode = str(data.get("permissionMode") or CLAUDE_WEB_PERMISSION_MODE or "default").strip()
    attachments = data.get("attachments") if isinstance(data.get("attachments"), list) else []
    original_prompt = _compose_prompt_with_attachments(prompt, attachments)
    prepared_prompt = _prepare_claude_prompt(original_prompt, mode, agent_mode)
    agent_name = _resolve_agent_name(agent_mode, prompt, mode)
    autonomous_mode = _should_autocontinue_chat(prompt, agent_mode)
    initial_prompt = _prepare_autonomous_chat_prompt(prepared_prompt) if autonomous_mode else prepared_prompt
    display_model = str(CLAUDE_MODE_CONFIG.get(mode, {}).get("model") or "").strip()

    def generate():
        try:
            current_session_id = session_id
            next_prompt = initial_prompt
            total_turns = CLAUDE_CHAT_MAX_AUTO_TURNS if autonomous_mode else 1
            if busy_session:
                yield json.dumps(
                    {
                        "type": "system_notice",
                        "message": "当前会话正在被后台任务占用，已自动切到新会话继续，避免聊天卡住。",
                        "busySessionId": requested_session_id,
                        "busyRun": busy_session,
                    },
                    ensure_ascii=False,
                ) + "\n"
            for turn_index in range(1, total_turns + 1):
                turn_done_event = None
                for event in _claude_stream_session(
                    CLAUDE_WRAPPER_PATH,
                    CLAUDE_WORKSPACE_ROOT,
                    next_prompt,
                    session_id=current_session_id,
                    agent_name=agent_name or None,
                    permission_mode=permission_mode,
                    add_dirs=_claude_allowed_dirs(),
                    timeout_seconds=CLAUDE_CHAT_TIMEOUT_SECONDS,
                ):
                    if (
                        mode == "opus46"
                        and isinstance(event, dict)
                        and event.get("type") == "session"
                        and display_model
                    ):
                        event = {**event, "model": display_model}
                    if event.get("type") == "session" and event.get("sessionId"):
                        current_session_id = str(event.get("sessionId") or current_session_id or "").strip()
                    elif event.get("type") == "done":
                        if event.get("sessionId"):
                            current_session_id = str(event.get("sessionId") or current_session_id or "").strip()
                        turn_done_event = event
                    yield json.dumps(event, ensure_ascii=False) + "\n"
                if not autonomous_mode:
                    break
                if not isinstance(turn_done_event, dict):
                    break
                run_state = _parse_autonomous_chat_run_state(
                    str(turn_done_event.get("result") or ""),
                    is_error=bool(turn_done_event.get("isError")),
                    stderr_text=str(turn_done_event.get("stderr") or ""),
                )
                if run_state != "CONTINUE":
                    break
                if turn_index >= total_turns:
                    break
                next_prompt = _prepare_claude_prompt(
                    _build_autonomous_chat_continue_prompt(
                        original_prompt=prompt,
                        turn_index=turn_index + 1,
                        last_result=str(turn_done_event.get("result") or ""),
                        last_error=str(turn_done_event.get("stderr") or ""),
                    ),
                    mode,
                    agent_mode,
                )
        except Exception as exc:
            _append_runtime_error_log(exc)
            yield json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n"

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson; charset=utf-8")


@app.route("/claude-console/stop-run", methods=["POST"])
def claude_console_stop_run():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    run_id = str(data.get("runId") or "").strip()
    if not run_id:
        return jsonify({"ok": False, "msg": "缺少 runId"}), 400
    result = _claude_stop_run(run_id)
    return jsonify(result), (200 if result.get("ok") else 404)


@app.route("/claude-console/open-session", methods=["POST"])
def claude_console_open_session():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    mode = _normalize_claude_mode(data.get("mode"))
    agent_mode = _normalize_agent_mode(data.get("agentMode"))
    prompt = str(data.get("prompt") or "")
    continue_latest = bool(data.get("continueLatest"))
    resume_session_id = str(data.get("sessionId") or "").strip()
    busy_session = _find_session_active_run(resume_session_id) if resume_session_id else None
    if busy_session:
        resume_session_id = ""
    permission_mode = str(data.get("permissionMode") or CLAUDE_WEB_PERMISSION_MODE or "default").strip()
    launch = _open_terminal_script(
        _write_terminal_script(mode, prompt, continue_latest, resume_session_id, agent_mode, permission_mode)
    )
    if not launch.get("ok"):
        return jsonify({"ok": False, "msg": launch.get("error") or "打开 Terminal 失败"}), 500
    return jsonify(
        {
            "ok": True,
            "mode": mode,
            "agentMode": agent_mode,
            "permissionMode": permission_mode,
            "continueLatest": continue_latest,
            "sessionId": resume_session_id or None,
            "detachedFromBusySession": bool(busy_session),
            "busyRun": busy_session,
            "launched": True,
            "scriptPath": launch.get("scriptPath"),
        }
    )


@app.route("/claude-console/quick-run", methods=["POST"])
def claude_console_quick_run():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    mode = _normalize_claude_mode(data.get("mode"))
    agent_mode = _normalize_agent_mode(data.get("agentMode"))
    permission_mode = str(data.get("permissionMode") or CLAUDE_WEB_PERMISSION_MODE or "default").strip()
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "msg": "请先输入 quick run 提示词"}), 400
    prepared_prompt = _prepare_claude_prompt(prompt, mode, agent_mode)
    agent_name = _resolve_agent_name(agent_mode, prompt, mode)
    started_at = datetime.now()
    command = [CLAUDE_WRAPPER_PATH]
    if permission_mode == "bypassPermissions":
        command.append("--dangerously-skip-permissions")
    command.extend(["--permission-mode", permission_mode])
    if agent_name:
        command.extend(["--agent", agent_name])
    for add_dir in _claude_allowed_dirs():
        if os.path.realpath(add_dir) == os.path.realpath(CLAUDE_WORKSPACE_ROOT):
            continue
        command.append(f"--add-dir={add_dir}")
    command.extend(["-p", prepared_prompt])
    result = _claude_run_capture(
        CLAUDE_WRAPPER_PATH,
        CLAUDE_WORKSPACE_ROOT,
        prepared_prompt,
        agent_name=agent_name or None,
        permission_mode=permission_mode,
        add_dirs=_claude_allowed_dirs(),
        timeout_seconds=CLAUDE_QUICK_RUN_TIMEOUT_SECONDS,
    )
    duration_ms = int((datetime.now() - started_at).total_seconds() * 1000)
    return jsonify(
        {
            "ok": bool(result.get("ok")),
            "mode": mode,
            "agentMode": agent_mode,
            "permissionMode": permission_mode,
            "transport": result.get("transport") or "unknown",
            "transportError": result.get("transportError") or "",
            "preparedPrompt": prepared_prompt,
            "durationMs": duration_ms,
            "stdout": result.get("stdout") or "",
            "stderr": result.get("stderr") or "",
            "returncode": result.get("returncode"),
            "timedOut": bool(result.get("timedOut")),
        }
    ), (200 if result.get("ok") else 500)


@app.route("/claude-console/settings", methods=["GET"])
def claude_console_settings():
    return jsonify(
        {
            "ok": True,
            "envFile": EASY_CLAUDECODE_ENV_FILE,
            "values": _load_editable_settings(),
            "installers": {
                "everythingClaudeCode": _everything_claude_code_status(),
            },
            "restartRequired": True,
        }
    )


@app.route("/claude-console/settings", methods=["POST"])
def claude_console_update_settings():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    raw_values = data.get("values")
    if not isinstance(raw_values, dict):
        return jsonify({"ok": False, "msg": "缺少 values"}), 400
    updates = {
        key: str(raw_values.get(key, EDITABLE_SETTINGS_DEFAULTS.get(key, "")) or "").strip()
        for key in EDITABLE_SETTINGS_FIELDS
    }
    _save_editable_settings(updates)
    sync_result = _sync_router_runtime()
    return jsonify(
        {
            "ok": True,
            "saved": True,
            "envFile": EASY_CLAUDECODE_ENV_FILE,
            "values": _load_editable_settings(),
            "installers": {
                "everythingClaudeCode": _everything_claude_code_status(),
            },
            "sync": sync_result,
            "restartRequired": True,
            "msg": "设置已保存。重启 Claude Code.app 后即可完整应用新的 API key 与上游配置。",
        }
    )


@app.route("/claude-console/installers/everything-claude-code", methods=["POST"])
def claude_console_install_everything_claude_code():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    try:
        payload = _run_everything_claude_code_install(
            target=str(data.get("target") or ECC_DEFAULT_TARGET),
            profile=str(data.get("profile") or ECC_DEFAULT_PROFILE),
        )
        return jsonify({"ok": True, "installer": "everything-claude-code", **payload})
    except ValueError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 400
    except FileNotFoundError:
        return jsonify({"ok": False, "msg": "installer script not found"}), 404
    except Exception as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 500


@app.route("/claude-console/open-location", methods=["POST"])
def claude_console_open_location():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "msg": "invalid json"}), 400
    target = str(data.get("target") or "").strip()
    allowed_targets = {
        "source-root": SOURCE_ROOT,
        "backend": os.path.join(SOURCE_ROOT, "services", "backend"),
        "workspace": CLAUDE_WORKSPACE_ROOT,
        "router-config": CLAUDE_ROUTER_CONFIG_FILE,
        "claude-user-config": CLAUDE_USER_SETTINGS_FILE,
        "claude-agents": os.path.join(CLAUDE_HOME_DIR, "agents"),
        "claude-plugins": CLAUDE_PLUGIN_ROOT,
        "router-errors": CLAUDE_ROUTER_ERR_LOG,
        "proxy-log": CLAUDE_PROXY_LOG,
        "proxy-errors": CLAUDE_PROXY_ERR_LOG,
    }
    open_target = allowed_targets.get(target)
    if not open_target:
        return jsonify({"ok": False, "msg": "非法 target"}), 400
    result = _open_local_path(open_target, reveal=False)
    if not result.get("ok"):
        return jsonify({"ok": False, "msg": result.get("msg") or "open failed"}), 500
    return jsonify({"ok": True, "target": target, "path": open_target})


if __name__ == "__main__":
    host = os.getenv("CLAUDE_CONSOLE_HOST", "127.0.0.1")
    port = int(os.getenv("CLAUDE_CONSOLE_PORT", "18882"))
    app.run(host=host, port=port, debug=False, threaded=True, use_reloader=False)
