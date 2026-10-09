# 运行方法

agent 读取 `local-notes.local.md` 使用已验收的 Python。以下命令从 skill 根目录执行，
`<python>` 代表实际解释器，不是可以原样执行的字符串。按本机 shell 正确引用路径，
不要借用作者的用户名、扩展 ID 或 ZotPilot 虚拟环境。

```text
<python> scripts/doctor.py
<python> scripts/workflow.py status
<python> scripts/workflow.py plan --input <清单.json> --target "课题 → 待读"
<python> scripts/workflow.py run --input <清单.json> --target "课题 → 待读" --out <新批次目录>
<python> scripts/workflow.py audit --input <清单.json> --target "课题 → 待读" --out <新核验文件.json>
<python> scripts/workflow.py resume --from <旧批次目录/manifest.json> --out <新恢复计划.json>
```

Windows PowerShell 用 `& $batchPython ...` 调用实际路径；macOS 用 `"$batchPython" ...`。
所有批次产物放在可写的本机私有目录；不能提交 Git。

输入：TXT 每行 DOI/URL；JSON 数组或 `{ "candidates": [...] }`。
项支持 `doi`、`title`、`landing_page_url`、`url`、`arxiv_id`。只有标题时先核对并解析。
目标可用 `→` 分隔的完整分类路径、唯一单名或 collection key。run 要求目标已在 Zotero 选中。
`--reuse-existing` 需要验证过的标签页复用能力。`--data-dir` 可覆盖本机配置。

输出：manifest 原始清单与文库身份，saves 保存日志，membership-plan/result 分类计划与结果，
audit 核验，report 汇总。输出目录必须新建或为空。保存请求前写进度；不保存密钥。

resume 只读真实文库。Server-ID 改变拒绝恢复；不确定提交又找不到条目时返回 blockers 和
退出码 2，不能删除 blocker 后盲目重投。已有条目缺 PDF 用补附件流程，不创建重复父条目。
恢复时沿用原 target 与 data_dir；重新执行使用新批次目录，保留旧报告。

## 补空字段

```text
<python> scripts/workflow.py metadata --input <patches.json> --target "课题 → 待读" --out <新目录>
```

默认仅生成计划；核对后换新目录并加 `--run`。输入示例：

```json
[{"item_key":"ABCD1234","identity":{"doi":"10.1234/example","title":"Verified paper title"},"source_url":"https://publisher.example/article/example","fields":{"abstractNote":"Verified abstract","pages":"1-12"}}]
```

示例是格式说明，不能直接执行。只补空字段，不覆盖 DOI、标题、作者、已有字段或分类。
先核实真实来源；缺摘要/作者等仍会使当前通用 audit 计为未完整，报告应区分元数据缺口与全文缺口。

当前自动核验对中文连续题名、短题名和扫描稿有限制。词重合只是线索，人工核验记录要保留，
不修改标题或降低阈值来通过验收。仅书目模式尚无独立 CLI 开关；用户只要书目时不要报告全文已完成。
