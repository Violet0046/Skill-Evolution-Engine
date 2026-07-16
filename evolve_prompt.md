# evolver agent

**任务**：根据建议对单个目标文件进行修复升级，把升级后的**完整文件**写到 `evidence/evolution_changes/需求分析Agent__agents__ReviewAgent__review_agent.md.change`。

## 目标文件

`/home/10358563/.claude/agents/Skill-Evolution-Engine/subjects/需求分析Agent/agents/ReviewAgent/review_agent.md` —— 要升级的文件路径（`Read` 拿当前内容，最终态写到 `.change`）。

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
      "id": "5527b413-affc-443e-862f-15ff6bb3f7d1-sg-002",
      "priority": "high",
      "direction": "ReviewAgent 在生成新审查结果文件时反复触发 Write:File has not been read yet 错误（review-agent 7 次），应明确区分「新建文件（直接 Write）」与「覆盖已有文件（先 Read）」两种流程",
      "evidence_uuids": [
        "437d64d4-55fc-4cd9-8964-f7becd69e1a8",
        "b15b9fc9-a461-48c8-8a0b-023c22f9092a",
        "593f0bcd-7b05-4ecc-9c84-07bc7bc0223a",
        "8edbef50-4ecd-4e53-ac10-5af2c99254b7",
        "f24a7d4a-d8ef-4c68-8e98-051fc18041b9",
        "4c3d73f9-fb15-4fd0-af5e-b37094e8136d",
        "e3117435-d9b3-4802-80d4-f471ceb6c7d7"
      ],
      "rationale": "review-agent 在 step_review/<subagentType>.review_result.json 等新文件时直接调用 Write，导致 7 次 <tool_use_error>File has not been read yet>。建议 review_agent.md 增加：输出审查结果前用 ls/Glob 检查文件是否存在 → 不存在则直接 Write；存在则先 Read 再 Write。"
    },
    {
      "id": "5527b413-affc-443e-862f-15ff6bb3f7d1-sg-010",
      "priority": "low",
      "direction": "review-agent 多次对目录路径调用 Read 触发 EISDIR，并对不存在的牵头子系统目录 ls 报 Exit code 2，应在文件存在性检查时优先用 Glob/ls -d",
      "evidence_uuids": [
        "3d65db5a-7b56-44f7-9a75-b1a2a1b8930f",
        "99b2f84e-7c1d-46ff-b29f-7545f00a849c",
        "999c39fd-7121-4172-bfcf-32790de221ab"
      ],
      "rationale": "review-agent 把目录当文件 Read（EISDIR）、对不存在的 牵头子系统/ 子目录直接 ls（Exit code 2）。建议 review_agent.md 增加：路径预检步骤——先用 Glob 或 ls -d 检查路径类型/存在性，再决定 Read/Write。"
    }
  ]
}
```

## 工作流

1. `Read /home/10358563/.claude/agents/Skill-Evolution-Engine/subjects/需求分析Agent/agents/ReviewAgent/review_agent.md` 拿当前内容
2. 按 priority 顺序读 suggestions（**不过滤任何 priority**）
3. 逐条应用到当前内容上，构造最终完整文件
4. 用 `Write` 工具写最终态到 `evidence/evolution_changes/需求分析Agent__agents__ReviewAgent__review_agent.md.change`
5. 输出 `<EVOLUTION_COMPLETE>` 或 `<EVOLUTION_FAILED>`

## 规则

### 禁止

- 写回被升级的源文件 —— 必须写 `.change`
- 读 `target_file` 之外的任何业务文件

### 反模式

- 输出 patch / diff 格式（期望完整最终态）
- 输出多个文件（一次只升级一个 target_file）
- 跳过 Read 直接写（缺上下文会改错）
- 自己拼路径（用占位符 `evidence/evolution_changes/需求分析Agent__agents__ReviewAgent__review_agent.md.change`）


## 完成后

最后一行输出 `<EVOLUTION_COMPLETE>` 或 `<EVOLUTION_FAILED>` + 原因。
