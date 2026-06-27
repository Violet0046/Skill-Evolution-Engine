分析指定skill的失败模式。

用户输入: $ARGUMENTS

## 执行步骤

### 步骤1：解析参数
从用户输入中提取：
- skill_name：skill名称（可选）
- output_dir：证据数据目录（可选，默认：当前目录下的output）

### 步骤2：执行分析
如果指定了skill_name：
```bash
bash ~/.claude/agents/Skill-Evolution-Engine/infra/analyze.sh output {skill_name}
```

如果没有指定skill_name：
```bash
bash ~/.claude/agents/Skill-Evolution-Engine/infra/analyze.sh output
```

### 步骤3：显示结果
显示脚本输出，不添加额外内容。

## 执行规则
- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
