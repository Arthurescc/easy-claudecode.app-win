$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HtmlPath = Join-Path $RepoRoot "apps\web\claude-console.html"
$PythonBin = (Get-Command python -ErrorAction Stop).Source
$env:SCROLL_SMOKE_HTML = $HtmlPath

@'
import os
from pathlib import Path

html = Path(os.environ["SCROLL_SMOKE_HTML"]).read_text(encoding="utf-8")

assert "messageScrollDetached" in html
assert "function syncMessageScrollState(" in html
assert "function scrollMessagesToBottom(" in html
assert "data-toggle-run-step" in html
assert "appState.forceMessageScroll" in html and "appState.messageScrollDetached" in html
assert "btn-scroll-bottom" in html

print("scroll autostick smoke ok")
'@ | & $PythonBin -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
