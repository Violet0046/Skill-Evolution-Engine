# 阶段 1 · 数据采集（simplify + 索引生成）

## 目标

把原始 Claude Code session 数据切成**轻量版 + 失败索引**，让 LLM 在阶段 2 可以**按需查询**而**不爆 context**。

## 与旧版的本质区别

| 旧版 | 新版 |
|---|---|
| 按 `Skill` 工具调用做栈式归因，把每条 tool_call 强行贴上 skill 标签 | **不归因**——只做字段精简 + 错误定位 |
| 写出 `output/{sid}/metadata.json + skills/*.json + summary.json` | 写出 `projects-simplified/{sid}.jsonl` + `.index/{sid}.json` |
| 主流程消费按 skill 预聚合的 JSON | 主流程消费**按需查询**的 3 个 `see_*` 工具 |

## 入口

```bash
PYTHONPATH=infra python infra/scripts/see-collect.py [<projects_dir> <projects_simplified_dir>]
```

参数：
- `<projects_dir>`：原始 session 目录（默认 `evidence/projects`）
- `<projects_simplified_dir>`：输出目录（默认 `evidence/projects-simplified`）

## 流程

1. **加载**——双格式自适应（NDJSON / JSON-array）
2. **分类**——给每条 entry 打 `entry_class` 标签（user_input / user_command / tool_result / ai_text / ai_tool_call / attachment.{subtype} / progress.{subtype} / ...）
3. **精简**——按 `infra/core/simplify/entry_fields_config.json` 的白名单 + 截断规则，砍掉冗余字段（type / sessionId / version / usage / 长 stdout/stderr 等）
4. **写出 NDJSON**——主文件用 JSON 数组格式（用户偏好可读），子文件用 NDJSON（节省 IO）；同步搬运 `subagents/*.meta.json`
5. **懒构建索引**——首次调 `see_failure_overview` 时自动构建 `.index/{sid}.json`；`--refresh` 强制重建

## 输出

```
evidence/projects-simplified/
├── {session_id}.jsonl                    # 简化版 session（首行 header，后续 entries）
├── {session_id}/subagents/agent-*.jsonl  # subagent NDJSON
├── {session_id}/subagents/agent-*.meta.json  # 角色元数据（agentType / description）
└── .index/{session_id}.json              # 失败索引（懒构建，~5KB）
```

## 索引 schema（v1.6）

```json
{
  "session_id": "...",
  "stats": {"total_entries": 2417, "total_errors": 27, "main_errors": 4, "sub_errors": 23, "subagent_files": 36},
  "by_pattern": {
    "Bash:Exit code 1": {
      "count": 8,
      "uuids": [
        {"uuid": "dbad6dda-...", "agent_id": null, "agent_type": "main"},
        {"uuid": "61be7587-...", "agent_id": "a1cd7b2c3f94f91b6", "agent_type": "差分场景检查单-agent"}
      ]
    }
  },
  "by_agent_type": {
    "main": {"errors": 4, "error_uuids": [...]},
    "差分场景检查单-agent": {"errors": 1, "error_uuids": [...]}
  }
}
```

## 完成条件

- `see-collect.py` 退出码 0，stdout JSON `status: "success"`
- `projects-simplified/{session_id}.jsonl` 存在
- `failure_analyzer overview <session_id>` 能返回有效 stats + top_patterns

## 失败模式

| 现象 | 原因 | 解决 |
|---|---|---|
| `输入目录不存在` | 路径错 | 检查 `projects_dir` |
| `no entries loaded` | 单文件解析失败 | 检查 JSON 格式 |
| `index load failed` | 索引构建异常 | `see-collect.py` 重跑一次即可重建 |

## 设计取舍

- **不归因**——新方法故意**不在 Python 阶段**给任何 tool_call 贴 skill 标签。skill 归因交给阶段 2 的 LLM，结合 reasoning（T1/T4）自主判断
- **不预聚合**——索引里只有 `by_pattern`（= 失败模式）和 `by_agent_type`（= subagent 角色），没有 `by_skill`（v1.6 删了，`attributionSkill` 不可靠）
- **索引懒构建**——见 `common/index_store.py`，源文件 mtime 变化自动失效
- **路径魔法保留**——`failure_analyzer` 内部用 `parents[3/4]` 推导项目根 + `evidence/projects-simplified`，挪动目录会断
