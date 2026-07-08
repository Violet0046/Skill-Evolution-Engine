# 阶段 1 · 数据采集（simplify）

## 目标

把原始 Claude Code session 数据切成**轻量版**。

## 入口

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-collect.py [<projects_dir> <projects_simplified_dir>]
```

参数：
- `<projects_dir>`：原始 session 目录（默认 `evidence/projects`）
- `<projects_simplified_dir>`：输出目录（默认 `evidence/projects-simplified`）

## 流程

1. **加载**——双格式自适应（NDJSON / JSON-array）
2. **分类**——给每条 entry 打 `entry_class` 标签
3. **精简**——按 `infra/core/simplify/entry_fields_config.json` 砍冗余字段
4. **写出**——主文件 JSON 数组、子文件 NDJSON；同步搬运 `subagents/*.meta.json`

## 输出

```
evidence/projects-simplified/
├── {session_id}.jsonl
└── {session_id}/subagents/
    ├── agent-*.jsonl
    └── agent-*.meta.json
```

### stdout JSON

```json
{
  "status": "success",
  "input_dir": "...",
  "output_dir": "...",
  "totals": { ... },
  "failed_sessions": [],
  "session_ids": [
    "<main session UUID 1>",
    "<main session UUID 2>"
  ]
}
```

**字段含义**：`session_ids` = 当前**成功处理**的 **main session UUID 列表**。

**用途**：作为**阶段 2 的批处理入口**——主 agent 在批处理模式下，从阶段 1 stdout 解析此字段，按顺序对每个 session_id 执行 `/see-analyze`。

## 完成条件

- `see-collect.py` 退出码 0，stdout JSON `status: "success"`
- `failed_sessions: []`

## 失败模式

| 现象 | 解决 |
|---|---|
| `输入目录不存在` | 检查 `projects_dir` |
| `no entries loaded` | 检查 JSON 格式 |
