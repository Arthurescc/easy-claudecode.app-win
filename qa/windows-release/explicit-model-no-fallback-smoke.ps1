$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$NodeBin = (Get-Command node).Source

@'
const http = require("node:http");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

async function listen(server) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  return `http://127.0.0.1:${address.port}`;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return {
    status: response.status,
    text: await response.text(),
  };
}

async function main() {
  const upstreamModels = [];
  const upstream = http.createServer(async (req, res) => {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const payload = JSON.parse(raw || "{}");
    upstreamModels.push(payload.model);
    if (payload.model === "MiniMax-M2.7-highspeed") {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { type: "provider_error", message: "your current token plan not support model (2061)" } }));
      return;
    }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      id: "chatcmpl-test",
      object: "chat.completion",
      created: Math.floor(Date.now() / 1000),
      model: payload.model,
      choices: [{ index: 0, message: { role: "assistant", content: "fallback should not happen" }, finish_reason: "stop" }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    }));
  });
  const upstreamUrl = await listen(upstream);

  const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "easy-claudecode-proxy-"));
  const proxyPort = 34609;
  const proxy = spawn(process.argv[2], [path.join(process.argv[3], "services", "backend", "claude_code_dashscope_proxy.js")], {
    cwd: process.argv[3],
    env: {
      ...process.env,
      CLAUDE_DASHSCOPE_PROXY_PORT: String(proxyPort),
      DASHSCOPE_CODINGPLAN_API_KEY: "test-key",
      CLAUDE_DASHSCOPE_PROXY_UPSTREAM: `${upstreamUrl}/v1/chat/completions`,
      EASY_CLAUDECODE_HOME: runtimeDir,
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("proxy health timeout")), 15000);
      const interval = setInterval(async () => {
        try {
          const response = await fetch(`http://127.0.0.1:${proxyPort}/health`);
          if (response.ok) {
            clearTimeout(timer);
            clearInterval(interval);
            resolve();
          }
        } catch {}
      }, 200);
      proxy.once("exit", (code) => {
        clearTimeout(timer);
        clearInterval(interval);
        reject(new Error(`proxy exited early: ${code}`));
      });
    });

    const response = await postJson(`http://127.0.0.1:${proxyPort}/v1/chat/completions`, {
      model: "MiniMax-M2.7-highspeed",
      stream: false,
      messages: [{ role: "user", content: "Reply with exactly strict-mode" }],
      openclawRoute: {
        selection: "explicit",
        routeId: "compatible-coding,MiniMax-M2.7-highspeed",
      },
    });

    if (response.status !== 500) {
      throw new Error(`expected 500, got ${response.status}: ${response.text}`);
    }
    if (upstreamModels.length !== 1) {
      throw new Error(`expected exactly one upstream attempt, got ${upstreamModels.length}: ${JSON.stringify(upstreamModels)}`);
    }
    if (upstreamModels[0] !== "MiniMax-M2.7-highspeed") {
      throw new Error(`expected strict request model, got ${JSON.stringify(upstreamModels)}`);
    }
    console.log(JSON.stringify({ attempts: upstreamModels }));
  } finally {
    proxy.kill("SIGTERM");
    upstream.close();
  }
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exitCode = 1;
});
'@ | & $NodeBin - $NodeBin $RepoRoot
