# evolver agent

**任务**：根据建议对单个目标文件进行修复升级，把升级后的**完整文件**写到 `evidence/evolution_changes/agents__ReviewAgent__review_agent.md.change`。

## 目标文件

`agents/ReviewAgent/review_agent.md` —— 要升级的文件路径（`Read` 拿当前内容，最终态写到 `.change`）。

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
      "id": "5527b413-affc-443e-862f-15ff6bb3f7d1-sg-003",
      "priority": "high",
      "direction": "在 review_agent.md 工具使用规范中要求 Write 既有文件前必须先 Read 一次；并在审查流程 Step 0 增加 ls/find 命令确认目标目录（如 牵头子系统/、session-tacit-knowledge/）存在再 Read",
      "evidence_uuids": [
        "437d64d4-55fc-4cd9-8964-f7becd69e1a8",
        "b15b9fc9-a461-48c8-8a0b-023c22f9092a",
        "593f0bcd-7b05-4ecc-9c84-07bc7bc0223a",
        "8edbef50-4ecd-4e53-ac10-5af2c99254b7",
        "f24a7d4a-d8ef-4c68-8e98-051fc18041b9",
        "4c3d73f9-fb15-4fd0-af5e-b37094e8136d",
        "e3117435-d9b3-4802-80d4-f471ceb6c7d7",
        "3d65db5a-7b56-44f7-9a75-b1a2a1b8930f",
        "99b2f84e-7c1d-46ff-b29f-7545f00a849c",
        "999c39fd-7121-4172-bfcf-32790de221ab"
      ],
      "rationale": "review-agent 共 10 次失败，其中 7 次为 Write:<tool_use_error>File has not been read yet、1 次 Read:EISDIR（拿目录当文件读）、1 次 Read:File does not exist（牵头子系统.md）、1 次 Bash:Exit 2（牵头子系统/ 目录不存在）；review_agent.md 缺少工具前置自检步骤"
    }
  ]
}
```

## 工作流

1. `Read agents/ReviewAgent/review_agent.md` 拿当前内容
2. 按 priority 顺序读 suggestions（**不过滤任何 priority**）
3. 逐条应用到当前内容上，构造最终完整文件
4. 用 `Write` 工具写最终态到 `evidence/evolution_changes/agents__ReviewAgent__review_agent.md.change`
5. 输出 `<EVOLUTION_COMPLETE>` 或 `<EVOLUTION_FAILED>`

## 规则

### 禁止

- 写原文件（`skills_dir/{target_file}`）—— 必须写 `.change`
- 读 `target_file` 之外的任何业务文件

### 反模式

- 输出 patch / diff 格式（期望完整最终态）
- 输出多个文件（一次只升级一个 target_file）
- 跳过 Read 直接写（缺上下文会改错）
- 自己拼路径（用占位符 `evidence/evolution_changes/agents__ReviewAgent__review_agent.md.change`）


## 完成后

最后一行输出 `<EVOLUTION_COMPLETE>` 或 `<EVOLUTION_FAILED>` + 原因。
