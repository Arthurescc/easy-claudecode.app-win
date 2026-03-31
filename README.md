# easy-claudecode.app-win

`easy-claudecode.app-win` 是一个把 Claude Code 从终端带到 App 端的项目。它为 Windows 提供更低门槛的桌面与 Web 控制台体验，让用户可以像使用 Codex App 一样使用 Claude Code，同时保留模型切换、会话管理、技能、自动化和本地路由能力。  
`easy-claudecode.app-win` brings Claude Code from the terminal into an app experience. It gives Windows users a lower-friction desktop and web console so they can use Claude Code more like Codex App, while still keeping model switching, thread management, skills, automations, and local routing.

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
   - `Copy-Item .env.example .env`
3. 安装 Python 依赖：
   - `py -3 -m venv .venv`
   - `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
4. 安装 Node 依赖：
   - `npm install`
5. 启动控制台：
   - `powershell -ExecutionPolicy Bypass -File .\\scripts\\open-claude-code.ps1`
6. 访问：
   - [http://127.0.0.1:18882/claude-console](http://127.0.0.1:18882/claude-console)

## 设置按钮 / Settings

Web 控制台右上角提供“设置”按钮，可直接修改常用 API key、上游地址、健康检查 URL 和全局界面语言。保存后重启 `Claude Code.app` 即可完整应用。  
The Settings button in the top-right corner lets users update API keys, upstream URLs, health-check URLs, and the global UI language. Restart `Claude Code.app` after saving to fully apply the changes.

## Windows 启动方式

仓库提供 PowerShell 启动链：

- `scripts\\open-claude-code.ps1`：拉起 Router / Proxy / Backend 并自动打开浏览器
- `scripts\\run-claude-console.ps1`：只运行后端
- `scripts\\start-claude-code-router.ps1`：只运行 Router
- `scripts\\start-claude-code-dashscope-proxy.ps1`：只运行本地代理

首次运行 `scripts\\open-claude-code.ps1` 或 `scripts\\open-claude-code.cmd` 时，仓库会自动构建 `apps\\desktop-windows\\bin\\Claude Code.app.exe`、创建或修复桌面快捷方式 `Claude Code.app.lnk`，并安装全局 `cc.cmd` 入口。双击桌面快捷方式时会直接打开独立 app 窗口，不再跳到默认浏览器标签页。

GitHub Releases 现在默认发布 Windows 安装器 `easy-claudecode.app-win-<version>-setup.exe`。安装器会提供桌面快捷方式、`cc.cmd` 和 `Everything Claude Code` 可选安装项，其中 ECC 默认不勾选，不会阻塞主应用安装。

前端工作台保持原版交互；模型切换走命令行 `cc switch`，例如：

```powershell
cc switch --list
cc switch MiniMax-M2.7-highspeed
cc switch dashscope-codingplan,glm-5
```

## Windows VM 回归

仓库内置了一套真实 Windows VM 的回归包，位置在：

- `qa/windows-vm/`

它用于在 Windows-on-ARM 虚拟机里验证共享目录、OEM 首启钩子、Python 安装和 `claude-console` 后端健康检查。详细说明见：

- [qa/windows-vm/README.md](qa/windows-vm/README.md)

## 发布产物

- 源码内打包：`npm run package:release`
- 主要产物：`dist/easy-claudecode.app-win-<version>-setup.exe`
- 附带 staging 目录：`dist/easy-claudecode.app-win-<version>/`

安装器内会继续保留开源版的可选 `Everything Claude Code` 安装入口，也可以在应用欢迎页和设置弹层里后装。

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
