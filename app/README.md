# 汇芯智能体中台 · 应用源码

唯一产品入口是「应用程序」里的「汇芯智能体中台」。39261 是桌面进程内部使用的本机端口，不提供普通浏览器入口。

- `server.py`：本机后台与执行引擎，只用 Python 3 标准库。
- `web/index.html`：工作台界面。
- `Desktop.swift`：macOS 原生窗口，负责启动和结束后台。
- `build-desktop.sh`：构建 `.app`，会把 `../bin/` 里的适配器一起打包进去。

业务数据默认在 `~/.local/share/huixin-agent-hub`：`hub.sqlite` 存任务索引，`workspace/tasks/` 存交付文件，`providers.json` 存模型配置，`secrets/` 存密钥，`server.log` 存后台日志。

交付文件里的 HTML、SVG 等主动内容一律按纯文本返回，避免以工作台身份执行其中的脚本。文件列表最多展示 100 个，单个文件查看上限 200 MB。

当前只在本机验证，使用 ad-hoc 签名。架构、安全与测试说明见上级目录的 README.md。
