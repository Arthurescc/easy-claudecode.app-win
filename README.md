# easy-claudecode.app-win

`easy-claudecode.app-win` 是一个脱敏后的 Claude Code 控制台开源版本。它把 Windows 启动链、Web 控制台、Flask 后端和可配置路由拆成一个独立仓库，默认不绑定任何个人运行环境。

## 目录

- `apps/web/`: Web 控制台入口
- `apps/desktop-windows/`: Windows 启动说明与入口
- `services/backend/`: Flask 后端和本地代理
- `config/router/`: Router 示例配置和自定义路由逻辑
- `scripts/`: 启动、同步、构建脚本
- `docs/`: 架构与安装说明

## 快速开始

1. 安装基础依赖：
   - `python3`
   - `node >= 20`
   - `claude` CLI（需按官方文档单独安装并完成登录）
   - `ccr` CLI（本仓库不内置，需自行安装到 PATH）
   - PowerShell 7 或 Windows PowerShell 5.1
2. 复制环境文件：
   - `cp .env.example .env`
3. 安装 Python 依赖：
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
4. 安装 Node 依赖：
   - `npm install`
5. 启动控制台：
   - `powershell -ExecutionPolicy Bypass -File .\\scripts\\open-claude-code.ps1`
6. 访问：
   - [http://127.0.0.1:18882/claude-console](http://127.0.0.1:18882/claude-console)

## 设置按钮

Web 控制台右上角提供“设置”按钮，可直接修改常用 API key、上游地址和健康检查 URL。保存后重启 `Claude Code.app` 即可完整应用。

## Windows 启动方式

仓库提供 PowerShell 启动链：

- `scripts\\open-claude-code.ps1`：拉起 Router / Proxy / Backend 并自动打开浏览器
- `scripts\\run-claude-console.ps1`：只运行后端
- `scripts\\start-claude-code-router.ps1`：只运行 Router
- `scripts\\start-claude-code-dashscope-proxy.ps1`：只运行本地代理

如果你希望把它固定到桌面，可以把 `scripts\\open-claude-code.ps1` 或 `scripts\\open-claude-code.cmd` 创建为快捷方式。

## 可选集成

公开版默认关闭外部调度桥接能力。如需自行启用，设置：

```bash
CLAUDE_CONSOLE_ENABLE_OPENCLAW=1
```

并通过 `.env` 补齐你自己的调度路径。

## 安全边界

本仓库不包含：

- 账号生成器
- 本机数据库、日志、缓存、生成物
- 个人 LaunchAgent / 私有任务投递链
- 任何 API key、token、cookie、密码

更多细节见 [docs/SETUP.md](docs/SETUP.md) 和 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。
