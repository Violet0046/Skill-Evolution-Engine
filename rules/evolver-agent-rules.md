### 禁止

- 写回被升级的源文件 —— 必须写 `.change`
- 读 `target_file` 之外的任何业务文件

### 反模式

- 输出 patch / diff 格式（期望完整最终态）
- 输出多个文件（一次只升级一个 target_file）
- 跳过 Read 直接写（缺上下文会改错）
- 自己拼路径（用占位符 `{{CHANGE_OUTPUT_DIR}}/{{CHANGE_FILENAME}}`）
