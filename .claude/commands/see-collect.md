执行数据采集。

用户输入: $ARGUMENTS

## 执行步骤

### 步骤1：解析参数
从用户输入中提取项目路径。

### 步骤2：执行采集
```bash
bash ~/.claude/agents/Skill-Evolution-Engine/infra/collect.sh {project_path}
```

### 步骤3：显示结果
显示脚本输出，不添加额外内容。

## 执行规则
- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
