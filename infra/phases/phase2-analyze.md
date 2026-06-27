# 阶段2：失败分析

## 目标

按 skill 维度分析失败模式，生成进化任务文件。

## 步骤1：获取 skill 列表

```bash
bash ~/.claude/agents/Skill-Evolution-Engine/infra/get_skills.sh <output_dir>
```

### 参数说明

- `<output_dir>`: 阶段1的输出目录

### 输出

- skill 名称列表（每行一个）

### 完成条件

返回至少 1 个 skill。

### 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| output目录不存在 | 路径错误 | 检查路径是否正确 |
| 返回 0 个 skill | session 中没有 skill 记录 | 检查 session 数据 |

## 步骤2：为每个 skill 生成分析任务

```bash
bash ~/.claude/agents/Skill-Evolution-Engine/infra/analyze.sh <output_dir> <skill_name>
```

### 参数说明

- `<output_dir>`: 阶段1的输出目录
- `<skill_name>`: 步骤1返回的 skill 名称

### 输出

- `tasks/{skill_name}.json` - 分析任务文件

### 完成条件

为所有 skill 生成任务文件。

### 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| skill 不存在 | 名称错误 | 使用 get_skills.sh 获取正确的名称 |

## 完成条件

所有 skill 都有对应的分析任务文件（脚本退出码为 0）。
