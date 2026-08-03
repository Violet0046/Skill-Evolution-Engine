### 禁止

- 写回被升级的源文件 —— 必须写 `.change`
- 读 `target_file` 之外的任何业务文件

### 反模式

- 输出 patch / diff 格式（期望完整最终态）
- 输出多个文件（一次只升级一个 target_file）
- 跳过 Read 直接写（缺上下文会改错）
- 自己拼路径（用占位符 `{{CHANGE_OUTPUT_DIR}}/{{CHANGE_FILENAME}}`）


###  写盘前的硬约束（重要）
 
在 `Write` `.change` / 目标 SKILL.md 之前必须遵守：
 
1. **必须先 `Read`** 现有 `.change` 或目标 SKILL.md，否则 `Write` 触发 `File has not been read yet`（工具硬约束不可绕过）
2. **禁止**用绝对路径写到隔离 worktree 的共享 checkout（如 `<projects_home>/<subject_name>/<target_file>`）——worktree 副本不可写共享绝对路径
3. 改用**相对路径**写到 `.change` 输出目录（默认 `evidence/<run_id>/evolution_changes/`），或 `cd` 后用相对路径写 worktree 副本