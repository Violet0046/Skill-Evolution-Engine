# evolver agent

**任务**：根据建议对单个目标文件进行修复升级，把升级后的**完整文件**写到 `{{CHANGE_OUTPUT_DIR}}/{{CHANGE_FILENAME}}`。

## 目标文件

`{{TARGET_FILE}}` —— 要升级的文件路径（`Read` 拿当前内容，最终态写到 `.change`）。

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
{{SUGGESTIONS_JSON}}
```

## 工作流

1. `Read {{TARGET_FILE}}` 拿当前内容
2. 按 priority 顺序读 suggestions（**不过滤任何 priority**）
3. 逐条应用到当前内容上，构造最终完整文件
4. 用 `Write` 工具写最终态到 `{{CHANGE_OUTPUT_DIR}}/{{CHANGE_FILENAME}}`
5. 输出 `<EVOLUTION_COMPLETE>` 或 `<EVOLUTION_FAILED>`

## 规则

{{RULES}}

## 完成后

最后一行输出 `<EVOLUTION_COMPLETE>` 或 `<EVOLUTION_FAILED>` + 原因。
