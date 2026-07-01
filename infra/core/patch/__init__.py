"""patch/ — OpenSpace 格式 Patch 解析与应用。

公开 API：
- parse_patch(patch_text)         → List[(file_path, ops)]
- apply_patch(skill_md_path, ops) → ApplyResult
- apply_patch_text(skill_md_path, patch_text) → ApplyResult  (便捷：parse + apply)
- ApplyResult = (success: bool, message: str, anchor_hits: int, anchor_misses: List[str])

Patch 格式：
```
*** Begin Patch
*** Update File: SKILL.md
@@ <锚点行>
 <上下文>
-<删除>
+<添加>
*** End Patch
```
"""
