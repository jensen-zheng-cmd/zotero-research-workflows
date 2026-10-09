---
name: zotero-local-batch
description: >-
  Add specified papers in batches to local Zotero through the user's authenticated
  browser and Connector, without cloud sync. Use for “添加论文到zotero”, “把这些论文放进
  Zotero”, “论文入库”, “这些 DOI 导入 Zotero”, “批量保存论文”, “add papers to Zotero”,
  and continuing an interrupted local import. For local-only imports prefer this
  over the cloud-dependent ZotPilot ingestion route. Pure paper discussion,
  literature discovery without ingestion, and unrelated library cleanup do not
  activate this skill.
---

# Zotero 本地批量入库

将用户指定的论文及可读全文 PDF 加入指定的本地分类，复用已有记录，保留原分类。
“添加论文 / 入库”默认包含 PDF；只有用户明确要求“仅书目 / 不要 PDF”才只保存元数据。
仅创建书目条目属于部分完成，不能报告“全部已添加”。
沿用用户语言。首次使用时说明正在使用本 skill。

## 执行入口

首次安装、迁移 Windows/macOS 或环境不通时，读[安装与修复](references/install.md)，
按本机事实配置并完成验收。普通入库不重装整个环境。
若存在 `references/local-notes.local.md`，先读其中已验收的 Python、目录和启动方式。
使用本 skill 的 `scripts/workflow.py`，避免重写临时程序。Python 与本机连接器位置见
[运行配置](references/runtime.md)和不提交的 `runtime.local.json`。参数与恢复见[运行方法](references/commands.md)。
脚本使用绝对路径，批次产物写到当前可写任务目录。
已有条目缺全文、浏览器桥接不可用或 RIS 只导入书目时，继续执行
[PDF 补附件流程](references/pdf-attachments.md)，不要以书目导入成功结束任务。

1. **输入与目标。** 用户已给清单和分类即授权执行，不再逐篇确认。只有标题时先查证并解析
   成 DOI 或真实论文页面，保留标题帮助核验。未给分类时查询当前选中分类；意图仍不明则简短
   询问目标。新检索出的候选先让用户选择一次整批，检索不自动等同于入库授权。
2. **预检和计划。** 运行 `status`、`plan`。以本地 API 实测、扩展心跳和选中目标为准；
   桥接状态的 `zotero_running:false` 单独不足以判定故障。支持个人文库；不启用云同步、
   不要求官网 API key。目标用完整分类路径或 collection key，重名须消歧。
3. **执行。** `run` 通过真实浏览器连接器逐篇保存，批量把匹配的已有/新条目加入目标分类，
   保留其他分类。保存期间选中分类不能改变。检查计划后执行，不再问泛泛的“是否继续”。
   本地写入可能出现 `Codex Zotero Local Batch` 授权窗口；请用户点击 Allow，等待原进程，
   不能再次启动同一批，也不要自动点击授权。
4. **核验。** 自动生成 audit；以文件可读、首页论文身份、作者/摘要和附件版本为依据。
   `saved_with_pdf` 仅表示低层文件头检查通过，不等于深度核验完成。缺字段时查出版社、作者
   或可靠文献数据库，用 `metadata` 的受限补字段入口写入后重跑 `audit`。不编造字段；
   早期在线发表缺卷期不是失败。
5. **报告。** 给出分类、新增/复用数、实际可读 PDF 数和未完成项，链接 report/audit。
   默认以“全部指定论文均有身份已核对的可读全文附件”作为完成条件。已下载到任务目录但未挂
   到 Zotero 父条目下不算入库完成；网页快照、摘要、空附件和 HTML 不算 PDF。
   无法取得全文时逐篇列标题、已检查来源和实际访问障碍，继续完成其余条目，不重复创建父条目。
   期刊元数据附着预印本 PDF 时明确说明；未指定出版社版时可接受明确标识的作者版。
   不主动做标签清理、笔记、索引或移动/删除原条目。

## 中断与验证

- 请求和 request_id 写入批次目录。中断后用 `resume` 读取原 `manifest.json` 与 `saves.json`，
  核对真实文库，再交给新批次；保留旧报告。
- `blocked`：请用户在原标签页完成登录/验证。收到完成回复后，用实际落地页 URL 和
  `--reuse-existing`；需扩展版本带 `+tabreuse`。不要反复另开验证页。
- `unconfirmed` 或提交中断而文库没有匹配：不能直接重试；核对请求结果、浏览器和文库。
  `resume` 会阻止未确认重投。已有条目缺 PDF 不能通过重建条目补附件。
- 缺 PDF：在已有条目上处理下载/附件并再次核验。不绕过登录、验证码或付费控制，不把网页
  HTML 当 PDF。用户已授权入库时，向匹配的原条目补合法可获取的全文属于授权范围，
  不再泛泛询问是否继续。出版社版优先；作者版/预印本须核对同一论文并明确版本。
  PDF 与正式刊文标题不同，先核对作者、摘要及方法，记录已验证的 PDF 标题，不能仅因关键词
  相似就接受。当前无法取得全文时只报告真实缺口，不宣称所有 PDF 已添加。
- 升级后先只读预检；需要维护时读运行环境说明。普通入库不顺便升级、安装 MCP 或重配扩展。

用户只需给清单和分类，保持 Zotero、已配置且具有机构权限的 Chrome/Edge 运行，处理实际登录/验证码及本地
授权。允许自然语言自动匹配；也可显式使用 `$zotero-local-batch`。
