进化指定skill。

用户输入: $ARGUMENTS

## 执行步骤

### 步骤1：解析参数
从用户输入中提取：
- skill_name：skill名称（必填）
- skills_dir：skills目录（可选，默认：当前目录下的skills）

### 步骤2：检查任务文件
```bash
ls -la tasks/{skill_name}.json 2>/dev/null || echo "任务文件不存在: tasks/{skill_name}.json"
```

如果任务文件不存在，提示用户先执行 `/see-analyze {skill_name}`。

### 步骤3：执行进化
```bash
bash ~/.claude/agents/Skill-Evolution-Engine/infra/evolve.sh tasks/{skill_name}.json skills
```

### 步骤4：显示结果
显示脚本输出，不添加额外内容。

## 执行规则
- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
