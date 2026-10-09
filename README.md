# Zotero Research Workflows

用 Codex 安装并适配本机的 Zotero 入库工作流，连接检索、全文核验与翻译阅读。

## 用 Codex 安装

**把下面这一整行直接复制给运行在你电脑上的 Codex：**

```text
请安装并配置 https://github.com/jensen-zheng-cmd/zotero-research-workflows 的 Zotero 本地批量入库 skill：先取得仓库本地副本并阅读 AGENTS.md 与 skills/zotero-local-batch/references/install.md，自行检查我的 Windows/macOS、Codex skill 目录、Python、Zotero 版本与数据目录、浏览器和现有扩展，补齐所需的 ZotPilot 本地桥接及 Connector，并按需应用标签页复用补丁；允许你为适配本机修改本地 skill、配置和必要脚本，先备份已有文件，不覆盖我的文库或其他工具配置。请直接推进安装、排错和验证，不要只给我教程；使用仓库公开示例，在独立的 Codex 安装验收分类中完成真实入库、PDF 身份核验和重复运行检查，测试条目保留供我查看。需要我登录、加载扩展、点击本地授权或解决无法自动处理的问题时，告诉我具体操作，等我完成后继续，直到验收通过；若有外部阻塞，保存进度并明确说明尚未完成。最后告诉我安装位置、实际测试结果，以及下次如何使用。
```

这是一条**发给 agent 的任务指令**，不是终端命令。需要在运行 Zotero 的同一台电脑上使用可执行本地命令的 Codex。远程云沙箱不能直接访问你电脑的 `localhost`。

你只需处理实际出现的登录、浏览器加载扩展和 Zotero 授权。Codex 负责探测、安装、适配、测试和恢复；不必先学会 Python、目录配置或桥接协议。已有 fork 就在 fork 中适配；没有 GitHub 账户也可以克隆或下载本地副本，**fork 不是使用前提**。

目标平台为 **Windows + macOS**，浏览器优先使用已有的 Chrome / Edge。Safari 不属于当前自动化安装路径。安装和测试完成前，agent 不能仅凭“依赖安装成功”宣称可用。当前交付的验证范围见 [验证记录](docs/validation.md)，包括尚未完成的真实平台验收。

## 这套仓库做什么

1. **检索与筛选**：用 Undermind 或其他入口找候选，再决定需要入库的论文。
2. **入库与核验**：可选用本仓库 skill，复用已有 Zotero 条目、追加分类、保存并核验全文。
3. **翻译与阅读**：把已核验的论文交给 Recto，或直接在 Zotero 阅读。

入库模块可以单独使用，不需要先购买或配置 Undermind、Recto、嵌入模型或 Zotero 云存储。不要求启用云同步；如果你本来开启了同步，本地修改仍可能随下一次同步上传。

## 安装后怎么用

把 DOI、论文链接或清单交给 Codex，例如：

> 使用 $zotero-local-batch，把这些论文加入“我的课题 → 待读”，保留原分类，补齐能合法取得的 PDF，并告诉我哪些仍缺全文。

保持 Zotero 和已登录的浏览器运行。登录/机构权限不会被 skill 自动获得。新增检索候选需要你选定一次，已有清单不需要逐篇重复确认。

## 不使用自动化也可以跟做

读 [基础工作流](docs/workflow.md)：官方 Connector 保存、手动核验和翻译交接。自动化是可选层，不是阅读教程的门槛。

## 给维护者

- [给 Codex 的安装与修复指南](skills/zotero-local-batch/references/install.md)
- [运行配置与 Windows / macOS 差异](skills/zotero-local-batch/references/runtime.md)
- [验证记录与已知限制](docs/validation.md)
- [依赖来源与许可说明](THIRD_PARTY_NOTICES.md)

首个公开测试版本：**v0.1.0-beta.1**。欢迎在 Windows / macOS 的真实环境试装；真实浏览器与文库验收仍由安装 agent 在你的电脑上完成。

[自动测试](https://github.com/jensen-zheng-cmd/zotero-research-workflows/actions) · [反馈安装问题](https://github.com/jensen-zheng-cmd/zotero-research-workflows/issues/new/choose) · [版本下载](https://github.com/jensen-zheng-cmd/zotero-research-workflows/releases)

仓库采用 **AGPL-3.0-or-later**，依赖及补丁来源见许可说明。第三方工具按其原许可分发，本仓库不打包浏览器登录态、论文全文或私人批次报告。
