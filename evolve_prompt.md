# evolver agent

**任务**：根据建议对单个目标文件进行修复升级，把升级后的**完整文件**写到 `evidence/2026-07-27-085446/evolution_changes/需求分析Agent__agents__协议分析-agent__协议分析-agent.md.change`。

## 目标文件

`/home/10358563/.claude/agents/Skill-Evolution-Engine/subjects/需求分析Agent/agents/协议分析-agent/协议分析-agent.md` —— 要升级的文件路径（`Read` 拿当前内容，最终态写到 `.change`）。

## 建议（输入）

每条建议字段含义：

| 字段 | 含义 |
|---|---|
| `id` | 唯一标识 |
| `priority` | 优先级：high > medium > low |
| `direction` | **修复方向**——一句话告诉你要做什么改动 |
| `rationale` | **理由**——为什么提这条建议，含现场证据 |
| `evidence_uuids` | 现场证据 UUID（**不需要自己去查**，rationale 已含关键证据）|

```json
{
  "suggestions": [
    {
      "id": "e22e6fd3-bf1d-454f-adb1-0ff02900cb0a-sg-020",
      "priority": "medium",
      "direction": "协议结果回填使用当前可用的文件工具，并在 Edit 不可用时采用 Read 后完整写入的回退流程。",
      "evidence_uuids": [
        "aab6847e-767f-4c9d-ad7c-638fbb4d8654"
      ],
      "rationale": "协议代理向 req_design_document.md 发起 Edit 时收到工具不可用；提示词应提供能力探测和安全回退，不应在不可用工具上重复尝试。"
    }
  ]
}
```

## 工作流

1. `Read /home/10358563/.claude/agents/Skill-Evolution-Engine/subjects/需求分析Agent/agents/协议分析-agent/协议分析-agent.md` 拿当前内容
2. 按 priority 顺序读 suggestions（**不过滤任何 priority**）
3. 逐条应用到当前内容上，构造最终完整文件
4. 用 `Write` 工具写最终态到 `evidence/2026-07-27-085446/evolution_changes/需求分析Agent__agents__协议分析-agent__协议分析-agent.md.change`
5. 输出 `<EVOLUTION_COMPLETE>` 或 `<EVOLUTION_FAILED>`

## 规则

### 禁止

- 写回被升级的源文件 —— 必须写 `.change`
- 读 `target_file` 之外的任何业务文件

### 反模式

- 输出 patch / diff 格式（期望完整最终态）
- 输出多个文件（一次只升级一个 target_file）
- 跳过 Read 直接写（缺上下文会改错）
- 自己拼路径（用占位符 `evidence/2026-07-27-085446/evolution_changes/需求分析Agent__agents__协议分析-agent__协议分析-agent.md.change`）


###  写盘前的硬约束（重要）
 
在 `Write` `.change` / 目标 SKILL.md 之前必须遵守：
 
1. **必须先 `Read`** 现有 `.change` 或目标 SKILL.md，否则 `Write` 触发 `File has not been read yet`（工具硬约束不可绕过）
2. **禁止**用绝对路径写到隔离 worktree 的共享 checkout（如 `<projects_home>/<subject_name>/<target_file>`）——worktree 副本不可写共享绝对路径
3. 改用**相对路径**写到 `.change` 输出目录（默认 `evidence/<run_id>/evolution_changes/`），或 `cd` 后用相对路径写 worktree 副本

## 完成后

最后一行输出 `<EVOLUTION_COMPLETE>` 或 `<EVOLUTION_FAILED>` + 原因。
