# 由 Codex 完成本机安装

目标：用户给出仓库地址后，在 Windows 或 macOS 上安装可调用的 skill，打通本地 API → ZotPilot bridge → 真实浏览器 Connector，并完成公开示例的入库、全文核验和重复运行验收。用户已经授权这一范围，直接推进；不要每做一步都问“是否继续”。

本指南给出目标、可靠来源和必要约束。具体目录、包管理器、浏览器、启动方式由你根据本机实际选择。现有可用环境优先复用；不要要求用户照抄作者电脑配置。

## 1. 建立可恢复的工作目录

取得用户指定仓库的本地副本，记录来源 URL 与 commit。已有 fork 时用 fork；没有 fork 时直接 clone/download，不因 GitHub 登录阻止安装。不自动创建远程 fork 或 push，除非用户另有要求。

在副本 `.local/install/` 下记录 `progress.json`：当前阶段、已完成动作、实际版本、下一步、阻塞、备份和测试产物路径。不存密钥、Cookie 或完整浏览器配置。开始恢复时先读它，再核对本机；文件记录不替代实时探测。

建议阶段：`discovered → dependencies_ready → connector_ready → configured → tests_passed → live_verified`。等待用户操作时记录 `needs_user_action` 和恢复阶段；缺网络/工具时为 `blocked`。只有最后阶段可以报告安装并验收完成。

## 2. 自动探测，不让用户先填环境问卷

- 确认当前执行环境就是运行 Zotero 的电脑；WSL/容器与宿主不是同一个 localhost，优先使用 Windows 原生解释器或 macOS 原生解释器，不开放网络端口来绕过隔离。
- 找到可用 Python 3.10+（优先 3.12）、git，以及需要补丁时的 Node.js。没有 Python 时按官方渠道安装用户级 Python/uv，或复用已有 uv；需要系统安装权限时才请求对应权限。
- 先用已有 Python 运行 `scripts/doctor.py`。诊断脚本只读本机的 profile 路径信息和本地 API，不读取完整 ZotPilot 配置或 token。不要将它的本机报告推送到仓库。
- 找到 Zotero 可执行文件与数据目录。区分程序目录、profile 目录、含 `zotero.sqlite` 的数据目录。多 profile/多个数据目录时，以当前运行实例或用户设置界面核对；脚本无法消歧时才询问，不猜第一个目录。
- 确认 Zotero 10+ 本地 API 可用。缺失时从 [Zotero 官网](https://www.zotero.org/download/) 准备安装；旧版本升级先说明并保留用户数据备份，不能只为安装强行升级现有文库。设置 → 高级 → 允许本机其他应用通信。用 API 的 Server-ID 核对运行文库。
- 复用用户平时用于论文登录的 Chrome/Edge profile，不创建没有机构登录态的新浏览器来代替。macOS 默认选已有 Chrome/Edge，不假定 Safari 支持当前加载方式。

`doctor.py` 只是诊断入口，不会安装依赖、启动进程、授权写入或宣称已完成真实验收。退出码 2 表示待解决项，不代表应停止整个安装任务。

## 3. 安装 skill 与独立运行环境

探测 Codex 当前的 skill 来源。官方通用用户位置是 `~/.agents/skills`；已有环境也可能使用 `~/.codex/skills` 或自定义路径。优先与当前客户端实际加载方式一致，避免在两个地方安装同名 skill。参考 [Codex 官方 skill 文档](https://learn.chatgpt.com/docs/build-skills)。

将 `skills/zotero-local-batch` 复制到选定的 skill 目录。已有同名 skill 时先检查它是否就是本项目和是否有用户修改，备份后合并所需修改；保留 `runtime.local.json`、本机注记及已有环境，不直接覆盖整目录。无写权限时走正常权限申请，不假装已安装。

在最终 skill 目录创建 `.venv`；安装 `requirements.txt` 中的已知基线。示例命令的 `python` 是你已找到的解释器，路径都应正确加引号：

```text
python -m venv <skill目录>/.venv
<venv-python> -m pip install -r <skill目录>/requirements.txt
```

Windows 的解释器位于 `.venv/Scripts/python.exe`，macOS 位于 `.venv/bin/python`。不要把安装目录写死到用户名或盘符。已有兼容环境可复用，但必须记录并验证版本；不要默认借用别的工具的虚拟环境。

这里只需要 ZotPilot 的 bridge 子命令。**不执行完整的 `zotpilot setup`、索引或 MCP 注册**；它们会引入本任务不需要的嵌入模型/账户配置。先查看当前 `zotpilot bridge --help`，使用该环境的可执行文件。

如果固定版本在当前平台无法安装，保留错误证据，查上游兼容版本并在本地调整 requirements/代码，再运行测试。不能只解除版本约束就宣称成功。把实际版本与原因记入本机注记。

## 4. 准备桥接和 Connector

来源：[ZotPilot 仓库](https://github.com/xunhe730/ZotPilot)、[v0.5.3 Release](https://github.com/xunhe730/ZotPilot/releases/tag/v0.5.3)。已核验的官方资产 URL、SHA256 和扩展内部路径固定在 [connector-release.json](connector-release.json)。优先使用准备脚本，自动下载、校验、解压、生成补丁、Node 语法检查并备份原文件：

```text
<venv-python> scripts/prepare_connector.py --out <本机稳定新目录>
```

输出的 `extension_directory` 才是浏览器应加载的目录（当前为 `build/manifestv3`），不是解压根目录。
如果下载因本机网络失败，agent 可通过浏览器或 gh 从同一官方 URL 获取 ZIP，再加 `--archive <已下载zip>`，脚本仍核对同一摘要。
脚本拒绝已有输出目录，避免覆盖已安装扩展。已有 `prepared.json` 时核对并复用，失败的半成品用新目录重试，不清理未知路径。
准备完成并不代表浏览器已加载，仍需后面的心跳和真实保存验收。
如果上游基线变更，核对来源与摘要后更新本地版本记录并重新测试；不要猜测下载 URL，也不要拿未构建的源码目录加载。

桥接与官方 Zotero Connector 不是一回事。官方扩展可保留用于手动保存；agent 自动化需要带 `/enqueue`、`/result` 协议的 ZotPilot Connector。扩展解压到稳定的本机目录，例如仓库 `.local/connector/`；保留 LICENSE。升级时保留旧副本。

先探测 `http://127.0.0.1:2619/status`：响应符合协议就复用，不能重复启动。端口被其他程序占用时确认身份；不要直接杀进程。桥接和扩展端口必须一致，仅修改客户端配置不能解决扩展端口不匹配。

需要启动时运行已安装的 `zotpilot bridge --port 2619`，监听本机地址，日志写 `.local/install/`。Windows 用隐藏窗口启动并记录进程 ID；macOS 用受控后台进程并记录 PID。启动后实测 `/status`；任务结束后进程是否仍存活也要核对。首版可提供经本机验证的启动脚本，不擅自安装登录自启服务。

在用户实际使用的浏览器中打开 `chrome://extensions` 或 `edge://extensions`，必要时请用户启用开发者模式并“加载已解压的扩展程序”。告诉用户准确目录和最少点击步骤。能准备的文件先全部准备好，再等待用户操作。以 bridge 的 `extension_connected` 与版本心跳判断连通，不能只看图标。`zotero_running:false` 需要结合本地 API 实测，不单独据此否定安装。

### 标签页复用补丁

先检查扩展是否已有兼容复用能力。当前工作流用心跳 `+tabreuse` 标记；若上游改为 capabilities，核对真实协议后适配本地工作流，不能伪造标记。

`prepare_connector.py` 已完成补丁和语法检查时无需重复应用。手工适配已有扩展时，定位真实 `agentAPI.js`，用本 skill 的脚本生成新文件：

```text
<venv-python> scripts/patch_connector.py --source <实际agentAPI.js> --out <临时新文件.js>
node --check <临时新文件.js>
```

检查 diff，确保按 origin/path/query 复用论文标签页，并且不关闭用户的已有标签页。备份原文件后再替换，重新加载扩展，等待新心跳。脚本按锚点拒绝未知源码：失败时读取实际处理器并做有依据的小范围适配，不盲目字符串替换、不重建整个扩展。测试与修改记录保留在 `.local/install/`。

若暂时不能完成复用补丁，普通保存可以继续验收，但必须报告“复用能力未完成”，不能报告完整安装成功。验证页面需要用户处理时沿用原页面，不无限新开标签。

## 5. 生成本机配置，允许必要适配

在已安装 skill 下运行：

```text
<venv-python> scripts/doctor.py --configure
```

它只在没有配置文件、数据目录唯一可确定时创建 `runtime.local.json`。多目录时先消歧，然后加 `--data-dir <已确认数据目录>`。已有配置不会被覆盖；要修改时备份并编辑 JSON。`ZOTERO_BATCH_CONFIG` 可指向另一份绝对路径配置。配置格式和字段见 [runtime.md](runtime.md)。

先用配置解决系统/目录差异；配置不能解决时可修改本地 skill 和辅助脚本，并补充有意义的测试。记录来源 commit、修改原因与如何重放。不得降低论文身份核验、删除不确定提交保护，或用作者目录替代本机发现。

把实际 Python、skill、扩展和启动命令写入 `references/local-notes.local.md`。普通入库时 skill 会先读此文件，因此新聊天不必重新探索整套环境。

## 6. 测试到真实用户表面

先运行该 skill 的 `test_*.py`（不连接真实文库）。然后从最终安装位置运行 `doctor.py --out <本机诊断.json>` 和 `workflow.py status`。记录每项结果；源码自测通过与浏览器心跳正常都不能代替真实保存。

README 安装指令已经授权：在个人文库的独立 `Codex 安装验收` 分类中，使用仓库公开示例做少量入库。先确认分类；不存在则通过 UI 或官方本地 API 创建，不直接改数据库。如果用户只要求只读安装，尊重这一更窄范围并将真实验收标为待完成。

1. 使用 [公开示例](../examples/smoke.json)，将复制到最终 skill 的示例作为输入。提前核对来源当前可访问。
2. 运行 `plan`，检查目标和预计新增/复用。将测试分类保持为 Zotero 当前选中分类。
3. 运行 `run`，使用新的本机批次目录。出现 `Codex Zotero Local Batch` 对话框时让用户 Allow，等待原进程，不再启动第二个任务。
4. `audit` 后打开 Zotero 的对应父条目和 PDF，核对题名、作者、首页与文件可读性。首页词重合只是线索；扫描稿/中文/改题版本需要人工证据，不降低阈值凑通过。
5. 再运行同一清单，使用新的输出目录；父条目数不得增加，原分类不得丢失，已有附件不得重复创建。已有示例论文可复用，但必须另外证明至少一次本次安装后的真实新保存；若样例都已在库，在公开来源选另一篇并核验，不删除旧条目以制造“新增”。
6. 对复用补丁，用同一论文的已打开落地页验证保存请求复用了该标签页并保留它；因为普通重复入库会跳过请求，不能拿“第二次 run 无重复”替代这项测试。需要时用扩展模拟测试，或选另一篇未在库的公开论文做一次真实复用保存。
7. 保留测试分类和条目供用户查看，不自行删除。将单测、doctor、真实 PDF、重复运行和复用结果写进安装进度。

最终答复包含安装位置、如何唤起 skill、如何启动桥接、实际版本、真实测试数量与未完成项。测试未全部完成时使用“已安装，待××验收”。

## 7. 排错与继续

| 现象 | agent 下一步 | 用户只需做什么 |
|---|---|---|
| API 不响应 / 403 | 核对程序与 API 设置、宿主/沙箱边界 | 必要时启动 Zotero 或启用本机通信 |
| bridge 正常、扩展断开 | 核对实际 profile、加载路径、心跳、端口 | 在所用浏览器加载/重新加载扩展 |
| 下载失败 | 核对官网、网络和包版本，保留已完成步骤 | 只有网络需人工处理时给出明确操作 |
| 多个数据目录 | 只读核对 profile 与当前运行实例 | 无法判定时确认设置中的数据目录 |
| 保存结果不确定 | 核对 request_id 和真实文库再恢复 | 不要求用户重复点击保存 |
| 登录 / 验证码 | 等待原页面，保留任务与批次 | 自己完成登录或验证 |
| 文件存在但身份不明 | 核对论文内容，标记待核验 | 必要时帮助判断具体版本 |
| 补丁锚点不匹配 | 查真实版本，适配并做语法/行为测试 | 只在必须重新加载时操作 |

同一错误无新证据时不机械重试。遇到当前权限、工具或网络无法解决的阻塞，保存已完成工作，说明最小下一步，等用户回应后继续。目标是尽可能一次委托完成，不承诺每台机器都无需交互。
