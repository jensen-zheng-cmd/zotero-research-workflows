# 向现有论文补全文附件

## 获取与身份核对

先查询父条目已有附件。读取真实本地文件，不能把附件元数据当作文件已存在。
依次检查出版社可访问全文、用户已登录的机构入口、作者主页/机构仓储、arXiv 等公开版本，
以及已连接的文献工具返回的 PDF。下载结果必须是可读全文；HTTP 200 可能只是登录页。
保留正式出版元数据，另行标明附件是出版社版、作者稿或预印本。

检查 PDF 首页题名、作者、摘要与目标论文。改题的作者版本需确认同一研究后记录 `pdf_title`。
自动题名词覆盖率仅作预检；扫描稿或标题变化不能靠降低阈值自动接受，应人工核对首页。
公开来源均不可获取时，保留原条目、说明具体访问障碍，继续其他论文；不要用相关论文替代。

## 写入方式与授权

浏览器 Connector 保存及下载仍是常规入口。若仅 RIS 入库成功，不能到此结束。
同一 Connector 导入会话仍有效且父条目映射明确时，可用其补附件接口；会话可能十分钟后
过期，也会因 Zotero 重启丢失。记录会话与返回条目 ID，不猜映射、不为补附件重建父条目。

没有有效会话时使用 Zotero 10 官方本地 API，创建原父条目的 stored attachment，完成
上传授权、上传字节、注册文件三个步骤，再核对 `storage` 下真实文件。不要直接写 Zotero 数据库。
原生 `Codex Zotero Local Batch` 窗口需要用户 Allow，可自行选择 Always Allow；不能自动代点。
授权等待时保留原任务进程，不开第二个写入任务。启动 Zotero 后要实测 API，隐藏启动但未
响应不表示可以继续；必要时在正常桌面环境启动，并让用户看到实际授权窗口。

官方依据：[本地 API](https://www.zotero.org/support/dev/web_api/v3/local_api)、
[附件上传](https://www.zotero.org/support/dev/web_api/v3/file_upload)。

## 可复用的 stored PDF 帮助脚本

使用本 skill 的 `scripts/attach_verified_pdfs.py`。输入 JSON 数组：

```json
[{"status":"downloaded","parent_key":"ABCD1234","title":"Verified published title",
  "path":"C:/task/paper.pdf","pdf_title":"Verified author manuscript title",
  "source_url":"https://arxiv.org/abs/xxxx.xxxxx","edition":"author_preprint"}]
```

`pdf_title` 仅在经过人工核对的改题版本中设置，其他论文省略。
`edition` 示例：`publisher_version`、`author_manuscript`、`author_preprint`。
只写已下载且核对的行；无法取得全文的行保留为 `unavailable` 供整批完成报告使用。

```text
<python> scripts/attach_verified_pdfs.py --input <pdfs.json> --collection ABCD1234 --out <新附件批次目录>
# 预检通过后，沿用原目录，加 --run 执行。
```

`<python>` 使用本机已验收的解释器；数据目录默认读取 `runtime.local.json`，也可传 `--data-dir`。
路径和引用方式由 agent 按 Windows / macOS 适配。当前补附件的标题自动检查以英文为主，
中文与扫描件需进一步适配并核验，不以降低阈值代替身份检查。

默认仅生成计划，无文库写入。执行前确认父条目标题、所属目标分类、PDF 可读及题名覆盖率。
对同一父条目已有的同 SHA256 文件跳过；保留写入进度以便中断恢复。创建请求结果不确定时
停止，先查文库再恢复，不能删除进度盲重试。密钥仅在进程内存，不写入产物。

结束后逐篇核对父条目子附件、存储路径、文件哈希、可读页数和论文身份。
正式标题与已验证作者稿标题不同的条目，报告这种对应关系；通用 audit 的标题匹配失败不能
被隐瞒，也不能自动覆盖正式题名。整批报告必须同时列出指定数量、已挂可读全文数量、缺失数量。
