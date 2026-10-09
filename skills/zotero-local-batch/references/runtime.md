# 本机运行配置

用户不需要手填这些字段；安装 agent 通过 [install.md](install.md) 探测、验证并生成。
每次调用前仍要运行 `workflow.py status`；安装记录不能替代当前状态。

## 路径与配置优先级

1. `ZOTERO_BATCH_CONFIG`：可选，指向绝对路径 JSON；显式指定却不存在时拒绝运行。
2. 默认：本 skill 根目录 `runtime.local.json`，不提交 Git。
3. 没有配置时，API/桥接使用本机默认端口；数据目录只在候选唯一时自动选择。

`--data-dir` 覆盖配置中的数据目录。端口只能是 loopback HTTP 地址，不能指向远程 Zotero。

```json
{
  "schema_version": 1,
  "api_base": "http://127.0.0.1:23119",
  "bridge_base": "http://127.0.0.1:2619",
  "data_dir": "/absolute/path/to/Zotero"
}
```

这是格式示例，agent 应生成真实绝对路径。Windows 路径用 `/` 或正确转义的 `\\`；不要复制示例路径。
解释器、扩展目录、浏览器 profile 和启动命令写入 `local-notes.local.md`，不放进 JSON。

## Windows / macOS

| 项目 | Windows | macOS |
|---|---|---|
| skill 默认位置 | 用户目录下 `.agents/skills`，结合客户端实际确认 | `~/.agents/skills`，结合客户端实际确认 |
| 独立 Python | `<skill>/.venv/Scripts/python.exe` | `<skill>/.venv/bin/python` |
| Zotero profile 候选 | `%APPDATA%/Zotero/Zotero/profiles.ini` | `~/Library/Application Support/Zotero/profiles.ini` |
| 默认数据目录候选 | 用户目录下 `Zotero` | `~/Zotero` |
| 浏览器 | 已有 Chrome / Edge | 已有 Chrome / Edge |
| 程序发现线索 | PATH、已安装应用、标准安装位置 | `/Applications/Zotero.app`、`~/Applications/Zotero.app` |

程序位置仅是发现线索；自定义数据目录从 profile 的 `prefs.js` 读取相关路径设置。
不打印完整 prefs.js。多个文库不能凭一个目录存在就判断为当前文库；结合运行 API 与界面确认。
新文库尚无附件目录时，不要求 `storage` 已存在；真实附件保存后再核验文件。

Python 3.10+；已知依赖基线在 `../requirements.txt`。保存与诊断主要用标准库，PDF 核验依赖 PyMuPDF。
桥接通过 ZotPilot CLI 启动，扩展单独安装。仅入库无需 ZotPilot 全量 setup、嵌入配置或 MCP 注册。

`doctor.py` 检查系统、解释器、包、本地 API、选中目标、bridge、Connector 心跳与复用标记；
它不会申请写入权限或执行测试入库。`environment_ready=true` 也不等于真实流程通过。

## 协议与授权

本地写入依赖 Zotero 10+，与官网 API key 无关。本地授权窗口由用户点击 Allow；
不能自动代点，不重复启动等待中的任务。脚本不持久化 key。

当前 `--reuse-existing` 使用 `+tabreuse` 心跳标记，扩展 manifest 版本可能不带后缀。
安装时检查补丁，普通入库不自动替换扩展。DOI 重定向后使用实际出版社落地页 URL，保留 DOI。

本地 API 请求跳过系统代理；网页保存使用用户真实浏览器与其访问权限。
不要求云同步，但已有同步设置仍会对本地修改生效。

依据：[Zotero Local API](https://www.zotero.org/support/dev/web_api/v3/local_api)、
[Codex skill 位置](https://learn.chatgpt.com/docs/build-skills)、
[ZotPilot](https://github.com/xunhe730/ZotPilot)。
