# 依赖来源

本仓库原创代码与文档：Copyright (c) 2026 jensen-zheng-cmd。按 [AGPL-3.0-or-later](LICENSE) 发布。
这不改变独立依赖各自的许可，也不代表本项目获 Zotero 或 ZotPilot 官方背书。

| 依赖 | 来源 | 用途 |
|---|---|---|
| Zotero | https://www.zotero.org/ | 桌面文库、本地 API |
| ZotPilot | https://github.com/xunhe730/ZotPilot | 本地 bridge CLI；已知基线 0.5.3 |
| ZotPilot Connector | 上述仓库 Release 中的扩展资产 | 浏览器自动保存，来自 Zotero Connector 的 fork |
| PyMuPDF | https://pymupdf.readthedocs.io/ | PDF 可读性与文本检查；已知基线 1.28.2 |
| Codex | https://learn.chatgpt.com/docs/build-skills | 执行安装和使用 skill |

安装时从来源下载第三方软件并保留其许可证。本仓库没有打包 ZotPilot、Connector 或 PyMuPDF 的实现。
`patch_connector.py` 含源自 ZotPilot Connector `agentAPI.js` 的定位上下文和修改片段。
原文件 Copyright © 2026 ZotPilot Contributors，许可为 AGPL-3.0-or-later；本仓库保留该声明。
来源：[ZotPilot v0.5.3 的 agentAPI.js](https://github.com/xunhe730/ZotPilot/blob/v0.5.3/connector/src/browserExt/agentAPI.js)。
Connector 上游版权及许可全文保存在 [Zotero-Connector-COPYING.txt](LICENSES/Zotero-Connector-COPYING.txt)。
ZotPilot Python 包的 MIT 许可不覆盖此扩展代码；准备扩展时保留上游包和许可证，不将其改称 MIT。

本仓库不保存用户的 Cookie、授权 key、机构登录态、全文 PDF 或私人文库。测试样例仅提供公开链接与元数据。
本机诊断含目录、文库/条目标识和环境信息，公开 issue 前脱敏。
