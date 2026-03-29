$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "common-env.ps1")

$NodeBin = if ($env:NODE_BIN) { $env:NODE_BIN } else { "node" }
Set-Location $env:EASY_CLAUDECODE_ROOT
& $NodeBin "services/backend/claude_code_dashscope_proxy.js"
