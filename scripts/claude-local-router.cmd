@echo off
setlocal
if "%ANTHROPIC_BASE_URL%"=="" set "ANTHROPIC_BASE_URL=http://127.0.0.1:3456"
if "%ANTHROPIC_AUTH_TOKEN%"=="" set "ANTHROPIC_AUTH_TOKEN=easy-claudecode-local-router"
if "%CLAUDE_REAL_BIN%"=="" (
  set "CLAUDE_REAL_BIN=claude"
)
call "%CLAUDE_REAL_BIN%" %*
