# 进化规则

## 进化类型

### FIX（修复）
- **触发条件**: Skill 指令有误、过时或不完整
- **行为**: 就地修复，同名同目录，新版本记录
- **输出**: Patch 格式的修改

### DERIVED（派生）
- **触发条件**: 执行中发现更优方案
- **行为**: 创建增强版本到新目录
- **输出**: 完整的新 SKILL.md

### CAPTURED（捕获）
- **触发条件**: 无 Skill 指导下发现可复用模式
- **行为**: 创建全新 Skill
- **输出**: 完整的新 SKILL.md

## 进化流程

1. **分析阶段**: 运行 `analyze.sh` 生成结构化分析结果
2. **任务生成**: 运行 `evolve.sh` 生成进化任务文件
3. **进化执行**: subagent 读取任务文件，选择对应的提示词模板
4. **质量评估**: subagent 自我评估进化结果
5. **应用保存**: 应用 Patch 或保存新 SKILL.md

## 质量评估标准

### 修复质量
- 是否解决了根本原因？
- 是否保持了整体结构？
- 是否只修改了必要的部分？

### 派生质量
- 是否比父 Skill 有实质性改进？
- 是否自包含？
- 名称是否与父 Skill 不同？

### 捕获质量
- 是否可泛化？
- 是否清晰可操作？
- 是否与现有 Skill 不重复？

## Anti-loop 机制

### 规则1: 避免重复进化
- 如果一个 Skill 刚被进化，需要至少 5 次新的执行数据才能再次评估
- 记录进化历史，避免短时间内重复进化同一 Skill

### 规则2: 避免无效进化
- 如果进化建议与最近的进化相同，跳过
- 如果失败率低于阈值（如 10%），跳过

### 规则3: 优先级排序
- FIX > DERIVED > CAPTURED
- 失败率高的 Skill 优先处理

## 进化任务文件格式

```json
{
  "task_type": "evolution",
  "evolution_type": "fix|derived|captured",
  "skill_name": "skill名称",
  "skill_content": "当前SKILL.md内容",
  "direction": "进化方向",
  "failure_context": "失败上下文",
  "prompt_template": "prompts/fix_evolution.md"
}
```
