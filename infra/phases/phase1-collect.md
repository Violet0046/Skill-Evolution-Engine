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

## 完成条件

- `see-collect.py` 退出码 0，stdout JSON `status: "success"`
- `failed_sessions: []`

## 失败模式

| 现象 | 解决 |
|---|---|
| `输入目录不存在` | 检查 `projects_dir` |
| `no entries loaded` | 检查 JSON 格式 |
