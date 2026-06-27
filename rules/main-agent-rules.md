# 主agent规则（调度层）

## 职责边界

主agent只负责**调度**，不负责分析和进化。

### 允许做的事

1. 运行 `get_skills.py` 获取所有skill名称
2. 逐个运行 `analyze.py` 分析每个skill
3. 将分析结果保存为任务文件（tasks/{skill_name}.json）
4. 分发任务给subagent
5. 汇总进化结果

### 禁止做的事

1. **禁止**分析失败模式的根因
2. **禁止**生成进化建议
3. **禁止**修改SKILL定义
4. **禁止**预设解决方案

## 工作流程

```
1. 运行 get_skills.py 获取skill列表
2. 对于每个skill：
   a. 运行 analyze.py {output_dir} {skill_name} --json > tasks/{skill_name}.json
   b. 将任务文件分发给subagent
3. 汇总subagent的进化结果
```

## 状态管理

- 使用 `status.json` 追踪进度
- 每完成一个skill，更新状态

## 错误处理

- 如果analyze.py执行失败，记录错误并继续下一个skill
- 如果subagent执行失败，记录错误并继续下一个skill
