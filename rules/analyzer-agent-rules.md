### 失败模式

| 现象 | 行为 |
|---|---|
| `see_find` 返 `matched: 0` | 跳过该 agent |
| `see_entry_detail` 返 `uuid not found` | 重选其他 hit，**不**退出 |
| `by_agent_type` 显示 0 errors | 输出空 `suggestions: []`，注明 "session 无失败可分析" |

### 硬约束

- 必走 `with-python.sh` 垫片 + 必带 `PYTHONPATH=infra`
- 禁读 `session.jsonl` 原文
- **禁硬编码路径去探查目标项目**——必须先 `Glob` 拿真实目录树，按真实名取
- **若必要**，允许用 `Glob` + `head` 读目标文件的 **frontmatter + 一级标题**（≤ 30 行）——仅用于**精准定位 direction 落点**
- 至少看 1 个 detail 才有 suggestions
- **每个 agent find 后**，**对每个独特 `failure_pattern` 至少 detail 一次**（**写 report 前**必须**完整**——**不**能只 find 就写）
- 每条 suggestion 必含 `evidence_uuids`（至少 1 个）
- `target_file` / `target_skill` **优先**从 `## AGENT_ARCH` 段的 `targets[]` 选（映射：`target_skill` ← `targets[].name`，`target_file` ← `targets[].path`）
- **不确定属于哪个 skill** 时**不要**硬写，`target_skill` / `target_file` **可留空**
- 禁凭空建议（看见 Bash:Exit code 1 就说"bash 用错了"）
- `target_file` **必须**等于 `## AGENT_ARCH` 中某条目的 `path` 字段值（精确字符串匹配）
- 如果工具调用失败的根因**不在 AGENT_ARCH 列出的任何文件**，则 `target_skill` 和 `target_file` **都留空**
- **禁止**把 `agent_cwd`、`session.jsonl` 路径、或任何含 `/home/` `\\` 路径写入 target_file 字段


### 归因三问（写每条 suggestion 前必答，**不**答完不写）

1. **谁在调工具**？看 `T2.tool_name` 的调用方——是 main / 哪个 sub-agent？`target_skill` **必须**从调用方选，**不**从 T4 字面挑字眼
2. **哪个工具失败**？看 `T2.tool_name`——**detail 工具本身不是失败方**
3. **错在哪一层**？**对号入座**，**不**要硬套：
   - 路径错（Glob 不存在 / Read 不存在）→ 改用 Glob
   - 参数错（中文/括号/空格）→ 加 shell 引用 / find -print0
   - 用法错（Read 探目录 / Write 未先 Read）→ 改工具用法
   - 工具限制（sub-agent 无 Edit）→ 改用 Write / Bash heredoc
   - **环境/脚本错（analyzer 自己写盘 SyntaxError）** → 改 analyzer 写盘方式（**严禁**套到"路径含中文"上）

### 写盘硬约束

- 输出文件 `REPORT_PATH` **必须**用 **Write 工具**一次写盘
- **严禁**用 Bash 嵌 `python3 -c "..."` 写 JSON——多层引号/反斜杠在 heredoc 里互相 escape 不可靠
- 若必走命令行（如需要 `json.dumps` 序列化复杂对象）：先 `Write` 临时 `.py` 脚本到 `evidence/<run_id>/`，再 `bash infra/scripts/with-python.sh python3 <tmp>.py`
