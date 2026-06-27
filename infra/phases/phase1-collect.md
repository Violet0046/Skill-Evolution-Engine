# 阶段1：数据采集

## 目标

从 sessions 目录中提取结构化证据到 output 目录。

## 脚本路径

```bash
bash ~/.claude/agents/Skill-Evolution-Engine/infra/collect.sh <sessions_path> [output_dir]
```

## 参数说明

- `<sessions_path>`: 包含 Claude Code 会话 session 数据的文件夹，或单个 session 数据文件（.jsonl 格式）
- `[output_dir]`: 可选，若用户并未指明，脚本会自动在当前工作目录下创建 `output` 文件夹作为输出目录

## 输入

- sessions 目录或文件，包含 .jsonl session 数据

## 输出

- `output/{session_id}/` 目录
- 每个 session 包含：
  - `metadata.json` - session 元数据
  - `summary.json` - session 摘要
  - `skills/*.json` - skill 调用记录

## 完成条件

脚本执行成功（退出码为 0）。
