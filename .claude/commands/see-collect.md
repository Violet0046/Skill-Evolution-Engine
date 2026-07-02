执行数据采集（阶段 1：原始 session → projects-simplified + 失败索引）。

用户输入: $ARGUMENTS

## 执行步骤

### 步骤 1：解析参数
从用户输入中提取：
- `projects_dir`：原始 session 目录（可选，默认 `evidence/projects`）
- `projects_simplified_dir`：输出目录（可选，默认 `evidence/projects-simplified`）

### 步骤 2：执行采集

工作目录为 Skill-Evolution-Engine 项目根：

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-collect.py [projects_dir] [projects_simplified_dir]
```

### 步骤 3：显示结果
显示脚本输出（JSON 摘要），不添加额外内容。

## 执行规则
- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
