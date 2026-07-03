### 失败模式

| 现象 | 行为 |
|---|---|
| `see_find` 返 `matched: 0` | 跳过该 agent |
| `see_entry_detail` 返 `uuid not found` | 重选其他 hit，**不**退出 |
| `by_agent_type` 显示 0 errors | 输出空 `suggestions: []`，注明 "session 无失败可分析" |

### 硬约束

- 必走 `with-python.sh` 垫片 + 必带 `PYTHONPATH=infra`
- 禁 Read 任何文件 / 禁读 session.jsonl 原文
- 至少看 1 个 detail 才有 suggestions
- **每个 agent find 后**，**对每个独特 `failure_pattern` 至少 detail 一次**（**写 report 前**必须**完整**——**不**能只 find 就写）
- 每条 suggestion 必含 `evidence_uuids`（至少 1 个）
- `target_file` / `target_skill` **优先**从 `## AGENT_ARCH` 段的 `targets[]` 选（映射：`target_skill` ← `targets[].name`，`target_file` ← `targets[].path`）
- **不确定属于哪个 skill** 时**不要**硬写，`target_skill` / `target_file` **可留空**
- 禁凭空建议（看见 Bash:Exit code 1 就说"bash 用错了"）
- 输出文件：REPORT_PATH（用 Write 工具一次写盘）
