# 给安装和维护此仓库的 agent

用户复制 README 的安装指令后，你负责完成本机可用的安装，而不是回一份让用户自己执行的教程。先读 `skills/zotero-local-batch/references/install.md`；它给出依赖来源、适配顺序与验收标准。

- 默认支持 Windows / macOS，基础教程与自动化可独立使用。仅安装本地入库所需能力，不顺便配置 ZotPilot 全库索引、嵌入服务、MCP、Undermind 或 Recto 账户。
- 根据本机证据决定具体命令。优先复用兼容的安装；必要时自行修复 skill 副本、补丁或启动脚本。不得为了通过测试降低 PDF 核验标准、掩盖不确定提交或删除测试。
- 本机路径写入 skill 内 `runtime.local.json`；适配说明写 `references/local-notes.local.md`。本机文件、虚拟环境、第三方扩展和测试批次均不提交。通用修复保留 diff 与测试依据。
- 已有 skill 或扩展先备份，核对真实目录后再更新；不修改 Zotero 数据库或覆盖用户浏览器配置，不关闭同步或杀掉用户进程。安装指令授权的是本机安装与独立测试分类中的示例入库，不包括推送、发布或上传私人日志。
- 对同一失败没有新证据时，停止盲目重试，给出具体阻塞和用户所需的最小操作。用户回应后读取原进度继续，不重开重复批次。需要交互不等于安装结束。
- 最终报告区分：文件已安装、环境已就绪、真实入库已验收。没有真实 PDF 与重复运行证据，只能报告“待验收”。

已有源码测试在 `skills/zotero-local-batch/scripts/test_*.py`。使用当前 skill 的 Python 环境运行 `python -B -m unittest discover -s skills/zotero-local-batch/scripts -p 'test_*.py' -v`。依赖与解释器安装由 agent 按指南完成。
