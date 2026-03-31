#!/usr/bin/env node

const http = require("node:http");
const { Readable } = require("node:stream");
const { Agent, setGlobalDispatcher, ProxyAgent } = require("undici");

const HOST = process.env.CLAUDE_DASHSCOPE_PROXY_HOST || "127.0.0.1";
const PORT = Number(process.env.CLAUDE_DASHSCOPE_PROXY_PORT || "3460");
const UPSTREAM_URL =
  process.env.CODING_COMPATIBLE_UPSTREAM ||
  process.env.CLAUDE_DASHSCOPE_PROXY_UPSTREAM ||
  "https://api.minimaxi.com/anthropic/v1/messages";
const API_KEY =
  process.env.CODING_COMPATIBLE_API_KEY ||
  process.env.DASHSCOPE_CODINGPLAN_API_KEY ||
  "";
const ANTHROPIC_VERSION =
  process.env.CLAUDE_DASHSCOPE_ANTHROPIC_VERSION || "2023-06-01";
const PROXY_URL =
  process.env.HTTPS_PROXY ||
  process.env.HTTP_PROXY ||
  process.env.ALL_PROXY ||
  process.env.https_proxy ||
  process.env.http_proxy ||
  process.env.all_proxy ||
  "";
const UPSTREAM_MODE = /\/(?:apps\/)?anthropic(?:\/v1\/messages)?$/i.test(UPSTREAM_URL)
  ? "anthropic"
  : "openai";
const REQUEST_TIMEOUT_MS = Number(
  process.env.CLAUDE_DASHSCOPE_PROXY_TIMEOUT_MS || "600000"
);
const UPSTREAM_CONNECT_TIMEOUT_MS = Number(
  process.env.CLAUDE_DASHSCOPE_PROXY_CONNECT_TIMEOUT_MS || "120000"
);
const UPSTREAM_HEADERS_TIMEOUT_MS = Number(
  process.env.CLAUDE_DASHSCOPE_PROXY_HEADERS_TIMEOUT_MS || "0"
);
const UPSTREAM_BODY_TIMEOUT_MS = Number(
  process.env.CLAUDE_DASHSCOPE_PROXY_BODY_TIMEOUT_MS || "0"
);
const STREAM_FIRST_BYTE_TIMEOUT_MS = Number(
  process.env.CLAUDE_DASHSCOPE_PROXY_STREAM_FIRST_BYTE_TIMEOUT_MS || "120000"
);
const STREAM_HEARTBEAT_MS = Number(
  process.env.CLAUDE_DASHSCOPE_PROXY_STREAM_HEARTBEAT_MS || "3000"
);
const UNSUPPORTED_MODEL_TTL_MS = Number(
  process.env.CLAUDE_DASHSCOPE_PROXY_UNSUPPORTED_MODEL_TTL_MS || "1800000"
);

const TEXT_REPLACEMENTS = [
  ['"$schema"', '"schema"'],
  ["'$schema'", "'schema'"],
  ['"$defs"', '"defs"'],
  ["'$defs'", "'defs'"],
  ['"$ref"', '"ref"'],
  ["'$ref'", "'ref'"],
  ['"$id"', '"id"'],
  ["'$id'", "'id'"],
  ['"$anchor"', '"anchor"'],
  ["'$anchor'", "'anchor'"],
  ['"$comment"', '"comment"'],
  ["'$comment'", "'comment'"]
];

const DEFAULT_REASONING = {
  "glm-5": "high",
  "qwen3-max-2026-01-23": "high",
  "qwen3-coder-plus": "medium",
  "kimi-k2.5": "medium",
  "qwen3.5-plus": "medium",
  "glm-4.7": "medium",
  "MiniMax-M2.5": "medium",
  "MiniMax-M2.7-highspeed": "medium"
};

const FORCE_NON_STREAM_MODELS = new Set(["qwen3-max-2026-01-23"]);
const UNSUPPORTED_MODEL_CACHE = new Map();

const MODEL_FALLBACKS = {
  "glm-5": ["qwen3-max-2026-01-23", "qwen3-coder-plus"],
  "qwen3-max-2026-01-23": ["glm-5", "qwen3-coder-plus"],
  "qwen3-coder-plus": ["qwen3-max-2026-01-23", "glm-5"],
  "kimi-k2.5": ["qwen3.5-plus"],
  "qwen3.5-plus": ["kimi-k2.5"],
  "glm-4.7": ["glm-5", "qwen3-max-2026-01-23"],
  "MiniMax-M2.5": ["MiniMax-M2.7-highspeed", "glm-5", "qwen3-max-2026-01-23"],
  "MiniMax-M2.7-highspeed": ["MiniMax-M2.5", "glm-5", "qwen3-max-2026-01-23"]
};

function resolveProviderLabel() {
  const lower = String(UPSTREAM_URL || "").toLowerCase();
  if (lower.includes("minimax")) return "minimax-compatible";
  if (lower.includes("openrouter")) return "openrouter-compatible";
  if (lower.includes("gemini")) return "gemini-compatible";
  if (lower.includes("moonshot")) return "moonshot-compatible";
  if (lower.includes("bigmodel") || lower.includes("zhipu")) return "zhipu-compatible";
  return "compatible-coding";
}

const PROVIDER_LABEL = resolveProviderLabel();

if (PROXY_URL && ProxyAgent) {
  setGlobalDispatcher(
    new ProxyAgent({
      uri: PROXY_URL,
      connect: {
        connectTimeout: UPSTREAM_CONNECT_TIMEOUT_MS
      }
    })
  );
} else {
  setGlobalDispatcher(
    new Agent({
      connectTimeout: UPSTREAM_CONNECT_TIMEOUT_MS,
      headersTimeout: UPSTREAM_HEADERS_TIMEOUT_MS,
      bodyTimeout: UPSTREAM_BODY_TIMEOUT_MS
    })
  );
}

function log(event, details = {}) {
  const payload = {
    ts: new Date().toISOString(),
    event,
    ...details
  };
  console.log(JSON.stringify(payload));
}

function normalizeEffort(value) {
  if (!value) return null;
  const lowered = String(value).toLowerCase();
  if (lowered === "max" || lowered === "xhigh") return "high";
  if (lowered === "minimal" || lowered === "off") return "low";
  if (lowered === "low" || lowered === "medium" || lowered === "high") {
    return lowered;
  }
  return null;
}

function sanitizeText(text) {
  let output = text;
  for (const [needle, replacement] of TEXT_REPLACEMENTS) {
    output = output.split(needle).join(replacement);
  }
  return output;
}

function sanitizeValue(value) {
  if (typeof value === "string") {
    return sanitizeText(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeValue(item));
  }
  if (!value || typeof value !== "object") {
    return value;
  }

  const next = {};
  for (const [key, child] of Object.entries(value)) {
    if (key === "cache_control") {
      continue;
    }
    next[key] = sanitizeValue(child);
  }
  return next;
}

function preparePayload(payload, model) {
  const prepared = sanitizeValue({
    ...payload,
    model
  });
  delete prepared.openclawRoute;

  const explicitEffort = normalizeEffort(
    prepared.reasoning_effort || prepared.reasoning?.effort
  );
  delete prepared.reasoning;
  prepared.reasoning_effort =
    explicitEffort || DEFAULT_REASONING[model] || "medium";

  if (typeof prepared.max_tokens !== "number" && typeof prepared.max_completion_tokens === "number") {
    prepared.max_tokens = prepared.max_completion_tokens;
  }
  delete prepared.max_completion_tokens;

  return prepared;
}

function isUnsupportedModelError(bodyText) {
  return /not support model|unsupported model|model[^"]+not support|model[^"]+unsupported|\(2061\)/i.test(
    bodyText || ""
  );
}

function rememberUnsupportedModel(model, bodyText) {
  if (!model || UNSUPPORTED_MODEL_TTL_MS <= 0) {
    return;
  }
  UNSUPPORTED_MODEL_CACHE.set(model, {
    expiresAt: Date.now() + UNSUPPORTED_MODEL_TTL_MS,
    reason: String(bodyText || "").slice(0, 500)
  });
}

function isModelTemporarilyUnsupported(model) {
  if (!model) {
    return false;
  }
  const entry = UNSUPPORTED_MODEL_CACHE.get(model);
  if (!entry) {
    return false;
  }
  if (entry.expiresAt <= Date.now()) {
    UNSUPPORTED_MODEL_CACHE.delete(model);
    return false;
  }
  return true;
}

function getAttemptModels(requestedModel, payload) {
  const selection = String(payload?.openclawRoute?.selection || "").trim().toLowerCase();
  if (selection === "explicit") {
    return requestedModel ? [requestedModel] : [];
  }
  const preferredModels = [requestedModel, ...(MODEL_FALLBACKS[requestedModel] || [])];
  const attemptModels = isModelTemporarilyUnsupported(requestedModel)
    ? [...(MODEL_FALLBACKS[requestedModel] || []), requestedModel]
    : preferredModels;
  return attemptModels.filter(
    (model, index) => model && attemptModels.indexOf(model) === index
  );
}

function shouldRetry(statusCode, bodyText) {
  if (statusCode === 401 || statusCode === 403) {
    return false;
  }
  if ([408, 409, 425, 429, 500, 502, 503, 504].includes(statusCode)) {
    return true;
  }
  return /Illegal group reference|system_error|timeout|temporar|overload|rate limit/i.test(
    bodyText || ""
  );
}

async function readRequestBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

async function sendUpstream(preparedPayload) {
  return fetch(UPSTREAM_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(preparedPayload),
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS)
  });
}

async function sendAnthropicUpstream(preparedPayload) {
  return fetch(UPSTREAM_URL, {
    method: "POST",
    headers: {
      "x-api-key": API_KEY,
      "anthropic-version": ANTHROPIC_VERSION,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(preparedPayload),
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS)
  });
}

async function relayRawResponse(
  res,
  upstreamResponse,
  requestedModel,
  attemptModel
) {
  const headers = {
    "Content-Type":
      upstreamResponse.headers.get("content-type") || "application/json",
    "x-proxy-model-requested": requestedModel,
    "x-proxy-model-used": attemptModel,
    Connection: "keep-alive"
  };
  const requestId = upstreamResponse.headers.get("x-request-id");
  if (requestId) headers["x-request-id"] = requestId;
  const cacheControl = upstreamResponse.headers.get("cache-control");
  if (cacheControl) headers["cache-control"] = cacheControl;
  res.writeHead(upstreamResponse.status, headers);
  if (upstreamResponse.body) {
    Readable.fromWeb(upstreamResponse.body).pipe(res);
  } else {
    res.end(await upstreamResponse.text());
  }
}

async function relayStreamWithGuard(
  res,
  upstreamResponse,
  attemptModel,
  requestedModel
) {
  if (!upstreamResponse.body) {
    return { ok: false, reason: "missing_body" };
  }

  const headers = {
    "Content-Type":
      upstreamResponse.headers.get("content-type") || "application/json",
    "x-proxy-model-requested": requestedModel,
    "x-proxy-model-used": attemptModel,
    Connection: "keep-alive"
  };
  const requestId = upstreamResponse.headers.get("x-request-id");
  if (requestId) {
    headers["x-request-id"] = requestId;
  }
  const cacheControl = upstreamResponse.headers.get("cache-control");
  if (cacheControl) {
    headers["cache-control"] = cacheControl;
  }

  let heartbeatTimer = null;
  try {
    res.writeHead(upstreamResponse.status, headers);
    heartbeatTimer = setInterval(() => {
      if (!res.writableEnded) {
        res.write(": heartbeat\n\n");
      }
    }, STREAM_HEARTBEAT_MS);

    const reader = upstreamResponse.body.getReader();
    let firstChunk;
    try {
      firstChunk = await Promise.race([
        reader.read(),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("first_byte_timeout")), STREAM_FIRST_BYTE_TIMEOUT_MS)
        )
      ]);
    } catch (error) {
      try {
        await reader.cancel(String(error));
      } catch (_) {}
      if (!res.writableEnded) {
        res.write(`data: ${JSON.stringify({ error: String(error) })}\n\n`);
        res.end();
      }
      return { ok: false, reason: String(error) };
    }

    if (!firstChunk || firstChunk.done || !firstChunk.value || firstChunk.value.length === 0) {
      try {
        await reader.cancel("empty_stream");
      } catch (_) {}
      if (!res.writableEnded) {
        res.write('data: {"error":"empty_stream"}\n\n');
        res.end();
      }
      return { ok: false, reason: "empty_stream" };
    }

    res.write(Buffer.from(firstChunk.value));
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      if (value && value.length) {
        res.write(Buffer.from(value));
      }
    }
    res.end();
    return { ok: true };
  } finally {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
    }
  }
}

function getAssistantText(responseJson) {
  const message = responseJson?.choices?.[0]?.message;
  const content = message?.content;
  if (typeof content === "string") {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (!item) return "";
        if (typeof item === "string") return item;
        if (typeof item.text === "string") return item.text;
        return "";
      })
      .join("");
  }
  return "";
}

function getAssistantReasoningText(responseJson) {
  const message = responseJson?.choices?.[0]?.message;
  const value =
    message?.reasoning_content ||
    responseJson?.choices?.[0]?.delta?.reasoning_content ||
    "";
  return typeof value === "string" ? value : "";
}

function getAssistantToolCalls(responseJson) {
  const toolCalls = responseJson?.choices?.[0]?.message?.tool_calls;
  return Array.isArray(toolCalls) ? toolCalls : [];
}

function chunkText(text, size = 96) {
  if (!text) return [];
  const chunks = [];
  for (let index = 0; index < text.length; index += size) {
    chunks.push(text.slice(index, index + size));
  }
  return chunks;
}

function writeSseChunk(res, payload) {
  res.write(`data: ${JSON.stringify(payload)}\n\n`);
}

function emitDeltaTextChunks(res, { responseId, created, attemptModel, field, text }) {
  for (const piece of chunkText(text)) {
    writeSseChunk(res, {
      id: responseId,
      object: "chat.completion.chunk",
      created,
      model: attemptModel,
      choices: [
        {
          index: 0,
          delta: {
            [field]: piece
          },
          finish_reason: null
        }
      ]
    });
  }
}

function emitToolCallChunks(res, { responseId, created, attemptModel, toolCalls }) {
  for (const [index, rawCall] of toolCalls.entries()) {
    if (!rawCall || typeof rawCall !== "object") {
      continue;
    }
    const toolType = rawCall.type || "function";
    const functionName =
      rawCall.function?.name ||
      rawCall.name ||
      "tool";
    const rawArgs =
      typeof rawCall.function?.arguments === "string"
        ? rawCall.function.arguments
        : JSON.stringify(rawCall.function?.arguments || rawCall.arguments || {});
    const argChunks = chunkText(rawArgs || "", 1024);
    const firstChunk = argChunks.shift() || "";
    writeSseChunk(res, {
      id: responseId,
      object: "chat.completion.chunk",
      created,
      model: attemptModel,
      choices: [
        {
          index: 0,
          delta: {
            tool_calls: [
              {
                index,
                id: rawCall.id || `tool-${Date.now()}-${index}`,
                type: toolType,
                function: {
                  name: functionName,
                  arguments: firstChunk
                }
              }
            ]
          },
          finish_reason: null
        }
      ]
    });
    for (const extraChunk of argChunks) {
      writeSseChunk(res, {
        id: responseId,
        object: "chat.completion.chunk",
        created,
        model: attemptModel,
        choices: [
          {
            index: 0,
            delta: {
              tool_calls: [
                {
                  index,
                  function: {
                    arguments: extraChunk
                  }
                }
              ]
            },
            finish_reason: null
          }
        ]
      });
    }
  }
}

function replayAsStream(res, responseJson, attemptModel, requestedModel) {
  const responseId = responseJson.id || `chatcmpl-proxy-${Date.now()}`;
  const created = responseJson.created || Math.floor(Date.now() / 1000);
  const text = getAssistantText(responseJson);
  const reasoningText = getAssistantReasoningText(responseJson);
  const toolCalls = getAssistantToolCalls(responseJson);
  const finishReason =
    responseJson?.choices?.[0]?.finish_reason ||
    (toolCalls.length ? "tool_calls" : "stop");

  res.writeHead(200, {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "x-proxy-model-requested": requestedModel,
    "x-proxy-model-used": attemptModel
  });

  writeSseChunk(res, {
    id: responseId,
    object: "chat.completion.chunk",
    created,
    model: attemptModel,
    choices: [
      {
        index: 0,
        delta: {
          role: "assistant",
          content: ""
        },
        finish_reason: null
      }
    ]
  });

  if (reasoningText) {
    emitDeltaTextChunks(res, {
      responseId,
      created,
      attemptModel,
      field: "reasoning_content",
      text: reasoningText
    });
  }

  if (text) {
    emitDeltaTextChunks(res, {
      responseId,
      created,
      attemptModel,
      field: "content",
      text
    });
  }

  if (toolCalls.length) {
    emitToolCallChunks(res, {
      responseId,
      created,
      attemptModel,
      toolCalls
    });
  }

  writeSseChunk(res, {
    id: responseId,
    object: "chat.completion.chunk",
    created,
    model: attemptModel,
    choices: [
      {
        index: 0,
        delta: {},
        finish_reason: finishReason
      }
    ]
  });
  res.write("data: [DONE]\n\n");
  res.end();
}

function writeJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(statusCode, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(body)
  });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    return writeJson(res, 200, {
      status: "ok",
      provider: PROVIDER_LABEL,
      upstream: UPSTREAM_URL,
      apiKeyPresent: Boolean(API_KEY),
      mode: UPSTREAM_MODE,
      proxyConfigured: Boolean(PROXY_URL)
    });
  }

  if (UPSTREAM_MODE === "anthropic" && req.method === "POST" && req.url === "/v1/messages") {
    if (!API_KEY) {
      return writeJson(res, 500, {
        error: {
          type: "config_error",
          message: "CODING_COMPATIBLE_API_KEY is not set"
        }
      });
    }

    let rawBody = "";
    try {
      rawBody = await readRequestBody(req);
    } catch (error) {
      log("read_error", { error: String(error) });
      return writeJson(res, 400, {
        error: {
          type: "bad_request",
          message: "failed to read request body"
        }
      });
    }

    let payload;
    try {
      payload = JSON.parse(rawBody);
    } catch (error) {
      log("parse_error", { error: String(error) });
      return writeJson(res, 400, {
        error: {
          type: "bad_request",
          message: "request body must be valid JSON"
        }
      });
    }

    const requestedModel = payload.model;
    if (!requestedModel) {
      return writeJson(res, 400, {
        error: {
          type: "bad_request",
          message: "model is required"
        }
      });
    }

    const attemptModels = getAttemptModels(requestedModel, payload);
    let lastFailure = null;

    for (const [index, attemptModel] of attemptModels.entries()) {
      const upstreamPayload = {
        ...sanitizeValue(payload),
        model: attemptModel
      };
      const isFallback = index > 0;
      log("attempt", {
        requestedModel,
        attemptModel,
        isFallback,
        mode: "anthropic",
        stream: Boolean(upstreamPayload.stream)
      });

      let upstreamResponse;
      try {
        upstreamResponse = await sendAnthropicUpstream(upstreamPayload);
      } catch (error) {
        lastFailure = {
          statusCode: 502,
          bodyText: JSON.stringify({
            error: {
              type: "proxy_upstream_error",
              message: String(error)
            }
          })
        };
        log("attempt_transport_error", {
          requestedModel,
          attemptModel,
          error: String(error)
        });
        continue;
      }

      if (upstreamResponse.ok) {
        log("attempt_success", {
          requestedModel,
          attemptModel,
          isFallback,
          mode: "anthropic"
        });
        await relayRawResponse(res, upstreamResponse, requestedModel, attemptModel);
        return;
      }

      const bodyText = await upstreamResponse.text();
      lastFailure = {
        statusCode: upstreamResponse.status,
        bodyText
      };
      if (isUnsupportedModelError(bodyText)) {
        rememberUnsupportedModel(attemptModel, bodyText);
      }
      log("attempt_failure", {
        requestedModel,
        attemptModel,
        isFallback,
        statusCode: upstreamResponse.status,
        bodyText: bodyText.slice(0, 500)
      });
      if (!shouldRetry(upstreamResponse.status, bodyText)) {
        break;
      }
    }

    const statusCode = lastFailure?.statusCode || 502;
    const bodyText =
      lastFailure?.bodyText ||
      JSON.stringify({
        error: {
          type: "proxy_error",
          message: "all upstream attempts failed"
        }
      });
    res.writeHead(statusCode, { "Content-Type": "application/json" });
    res.end(bodyText);
    return;
  }

  if (req.method !== "POST" || req.url !== "/v1/chat/completions") {
    return writeJson(res, 404, { error: "not_found" });
  }

  if (!API_KEY) {
      return writeJson(res, 500, {
        error: {
          type: "config_error",
          message: "CODING_COMPATIBLE_API_KEY is not set"
        }
      });
    }

  let rawBody = "";
  try {
    rawBody = await readRequestBody(req);
  } catch (error) {
    log("read_error", { error: String(error) });
    return writeJson(res, 400, {
      error: {
        type: "bad_request",
        message: "failed to read request body"
      }
    });
  }

  let payload;
  try {
    payload = JSON.parse(rawBody);
  } catch (error) {
    log("parse_error", { error: String(error) });
    return writeJson(res, 400, {
      error: {
        type: "bad_request",
        message: "request body must be valid JSON"
      }
    });
  }

  const requestedModel = payload.model;
  if (!requestedModel) {
    return writeJson(res, 400, {
      error: {
        type: "bad_request",
        message: "model is required"
      }
    });
  }

  const attemptModels = getAttemptModels(requestedModel, payload);
  const forcedFailureModel = Array.isArray(req.headers["x-openclaw-force-fail-model"])
    ? req.headers["x-openclaw-force-fail-model"][0]
    : req.headers["x-openclaw-force-fail-model"];
  let lastFailure = null;

  for (const [index, attemptModel] of attemptModels.entries()) {
    const preparedPayload = preparePayload(payload, attemptModel);
    const useSyntheticStream =
      Boolean(preparedPayload.stream) && FORCE_NON_STREAM_MODELS.has(attemptModel);
    const upstreamPayload = useSyntheticStream
      ? { ...preparedPayload, stream: false }
      : preparedPayload;
    const isFallback = index > 0;
    log("attempt", {
      requestedModel,
      attemptModel,
      isFallback,
      stream: Boolean(preparedPayload.stream),
      syntheticStream: useSyntheticStream,
      reasoningEffort: preparedPayload.reasoning_effort
    });

    if (forcedFailureModel && forcedFailureModel === attemptModel) {
      lastFailure = {
        statusCode: 503,
        bodyText: JSON.stringify({
          error: {
            type: "forced_failure",
            message: `forced failure for ${attemptModel}`
          }
        })
      };
      log("attempt_forced_failure", {
        requestedModel,
        attemptModel,
        isFallback
      });
      continue;
    }

    let upstreamResponse;
    try {
      upstreamResponse = await sendUpstream(upstreamPayload);
    } catch (error) {
      lastFailure = {
        statusCode: 502,
        bodyText: JSON.stringify({
          error: {
            type: "proxy_upstream_error",
            message: String(error)
          }
        })
      };
      log("attempt_transport_error", {
        requestedModel,
        attemptModel,
        error: String(error)
      });
      continue;
    }

    if (upstreamResponse.ok) {
      if (useSyntheticStream) {
        const responseJson = await upstreamResponse.json();
        log("attempt_success", {
          requestedModel,
          attemptModel,
          isFallback,
          syntheticStream: true
        });
        replayAsStream(res, responseJson, attemptModel, requestedModel);
        return;
      }
      if (preparedPayload.stream) {
        const guarded = await relayStreamWithGuard(
          res,
          upstreamResponse,
          attemptModel,
          requestedModel
        );
        if (guarded.ok) {
          log("attempt_success", {
            requestedModel,
            attemptModel,
            isFallback
          });
          return;
        }
        log("attempt_stream_guard_retry", {
          requestedModel,
          attemptModel,
          isFallback,
          reason: guarded.reason
        });
        try {
          const recoveryPayload = { ...preparedPayload, stream: false };
          const recoveryResponse = await sendUpstream(recoveryPayload);
          if (recoveryResponse.ok) {
            const responseJson = await recoveryResponse.json();
            log("attempt_success", {
              requestedModel,
              attemptModel,
              isFallback,
              syntheticStream: true,
              recoveredFromStream: true
            });
            replayAsStream(res, responseJson, attemptModel, requestedModel);
            return;
          }
          const recoveryBodyText = await recoveryResponse.text();
          lastFailure = {
            statusCode: recoveryResponse.status,
            bodyText: recoveryBodyText
          };
          log("attempt_failure", {
            requestedModel,
            attemptModel,
            isFallback,
            statusCode: recoveryResponse.status,
            bodyText: recoveryBodyText.slice(0, 500),
            recoveryFromStream: true
          });
          if (!shouldRetry(recoveryResponse.status, recoveryBodyText)) {
            break;
          }
          continue;
        } catch (error) {
          lastFailure = {
            statusCode: 502,
            bodyText: JSON.stringify({
              error: {
                type: "proxy_stream_guard_error",
                message: String(error)
              }
            })
          };
          log("attempt_transport_error", {
            requestedModel,
            attemptModel,
            error: String(error),
            recoveryFromStream: true
          });
          continue;
        }
      }

      const headers = {
        "Content-Type":
          upstreamResponse.headers.get("content-type") || "application/json",
        "x-proxy-model-requested": requestedModel,
        "x-proxy-model-used": attemptModel
      };
      const requestId = upstreamResponse.headers.get("x-request-id");
      if (requestId) {
        headers["x-request-id"] = requestId;
      }
      const cacheControl = upstreamResponse.headers.get("cache-control");
      if (cacheControl) {
        headers["cache-control"] = cacheControl;
      }

      res.writeHead(upstreamResponse.status, headers);
      log("attempt_success", {
        requestedModel,
        attemptModel,
        isFallback
      });

      if (upstreamResponse.body) {
        Readable.fromWeb(upstreamResponse.body).pipe(res);
      } else {
        res.end(await upstreamResponse.text());
      }
      return;
    }

    const bodyText = await upstreamResponse.text();
    lastFailure = {
      statusCode: upstreamResponse.status,
      bodyText
    };
    if (isUnsupportedModelError(bodyText)) {
      rememberUnsupportedModel(attemptModel, bodyText);
    }
    log("attempt_failure", {
      requestedModel,
      attemptModel,
      isFallback,
      statusCode: upstreamResponse.status,
      bodyText: bodyText.slice(0, 500)
    });

    if (!shouldRetry(upstreamResponse.status, bodyText)) {
      break;
    }
  }

  const statusCode = lastFailure?.statusCode || 502;
  const bodyText =
    lastFailure?.bodyText ||
    JSON.stringify({
      error: {
        type: "proxy_error",
        message: "all model attempts failed"
      }
    });
  res.writeHead(statusCode, {
    "Content-Type": "application/json",
    "x-proxy-model-requested": requestedModel
  });
  res.end(bodyText);
});

server.listen(PORT, HOST, () => {
  log("listening", {
    host: HOST,
    port: PORT,
    upstream: UPSTREAM_URL
  });
});

server.requestTimeout = REQUEST_TIMEOUT_MS + 30000;
server.headersTimeout = REQUEST_TIMEOUT_MS + 60000;
server.keepAliveTimeout = Math.max(STREAM_HEARTBEAT_MS * 2, 30000);
