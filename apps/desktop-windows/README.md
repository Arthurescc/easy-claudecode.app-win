# easy-claudecode.app-win desktop entry

这个目录提供 Windows 侧的桌面入口说明。

推荐做法：

1. 将 `scripts/open-claude-code.cmd` 创建快捷方式到桌面。
2. 首次运行前先复制 `.env.example` 为 `.env`，填入你的 API key。
3. 双击快捷方式后，仓库会自动拉起 Router、Proxy、Backend，并在默认浏览器打开控制台。

如果你需要将它进一步封装成 `.exe`，可以在此目录基础上接入 `WebView2`、`Tauri` 或 `Electron`，但公开版默认保持轻量浏览器壳。
