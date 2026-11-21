# 汇芯智能体中台

> 版本 0.5.0 · 2026-11-21 · 汇芯内部自用

汇芯内部使用的 AI 业务工作台。它把 Codex、Antigravity、WorkBuddy 三套本机智能体放进同一个中文桌面窗口，按业务类别统一派活、追问和审批，交付文件自动归档到每个任务自己的目录。

本系统只供汇芯自己使用。给客户做的定制开发另起项目，不复用本系统的实例、账号和数据。

## 为什么自己做，而不是直接用现成工具

| 现成的多智能体客户端 | 汇芯智能体中台 |
|---|---|
| 按「会话」组织，业务一多就乱 | 按六类业务组织：内容生产、企业商单、课程交付、技能开发、经营管理、系统维护 |
| 依赖第三方桌面程序，对方升级或停更就受影响 | 直接对接各家官方命令行和 ACP 协议，不依赖任何中间客户端 |
| 回复结束就算完成 | 每个任务一个交付目录，按文件验收，原始需求留档 |
| 审批要切到别的软件里点 | 审批在中台里直接弹出，等你拍板 |

## 架构

```text
macOS 桌面窗口（Desktop.swift + WKWebView）
        │  仅本机 127.0.0.1:39261，Cookie + 请求令牌校验
        ▼
本机后台 server.py（Python 标准库，无第三方依赖）
   ├─ 任务库 SQLite：~/.local/share/huixin-agent-hub/hub.sqlite
   ├─ 交付目录：workspace/tasks/<任务编号>/交付物/
   └─ 执行引擎
        ├─ Codex        → codex exec --json（工作区可写沙箱）
        ├─ Antigravity  → agy acp（ACP JSON-RPC 2.0）
        └─ WorkBuddy    → bin/workbuddy-acp（ACP JSON-RPC 2.0）
```

## 安全与审批

- **审批交给人**：ACP 引擎在 `auto` 模式下自动执行常规编辑和安全命令；遇到删除、发布、远程修改这类高风险操作会发起审批，中台把请求原样弹给你，可选允许、拒绝或取消，30 分钟没有处理就自动取消。中台自己不会替你批准。
- **Codex 在沙箱里跑**：使用 `workspace-write` 沙箱，越出工作区的命令会直接失败，不会被自动放行。
- **停止会彻底结束**：每个任务的引擎都在独立进程组里运行，点「停止执行」会把整组进程一起结束。
- **排障日志不对外展示**：每个任务的引擎输出写入 `tasks/<编号>/.engine.log`，不出现在交付文件列表里。
- **密钥不入库**：WorkBuddy 专用密钥放在 `~/.local/share/huixin-agent-hub/secrets/`（权限 0600），由适配器启动时读取，不进入代码、日志和仓库。
- **只允许本机访问**：后台只监听本机地址，并校验 Host、Origin、Cookie 和请求令牌；普通浏览器打开会被拒绝。

## 使用

1. 运行 `zsh app/build-desktop.sh` 构建桌面应用，然后复制到「应用程序」。
2. 打开「汇芯智能体中台」，选好业务类别、执行工具和模型，描述需求后发送。
3. 智能体发起审批时，对话区会出现审批卡片，点选后任务继续执行。

前提：本机已安装并登录 Codex CLI、Antigravity CLI（`agy`）、WorkBuddy 桌面版，三者装一个就能用。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

测试用 `tests/fake_acp.py` 模拟智能体，不消耗模型额度。覆盖新建任务、追问不混入旧回复、审批允许和取消、执行中禁止追问、停止结束进程、等待审批时停止、旧版会话自动带上历史续接、日志隐藏、密钥脱敏。

## 目录

```text
app/server.py          本机后台与执行引擎
app/web/index.html     工作台界面
app/Desktop.swift      macOS 桌面窗口
app/build-desktop.sh   构建脚本
bin/workbuddy-acp      WorkBuddy ACP 启动适配
bin/acp_stdio_bridge.py 过滤启动横幅，保证协议通道干净
tests/                 回归测试
制作状态.md             当前进度、核验证据与未完成项（接手前必读）
```

## 致谢

界面布局参考了 [zds-xiaoxin/xiaoxin-t3code](https://github.com/zds-xiaoxin/xiaoxin-t3code)（MIT）的设计思路。0.4.0 起执行层由中台自研，不包含、也不依赖 T3 Code 的代码。

---

**出品：袁六伟 · 台州汇芯**（公众号 / 视频号：袁六伟）
