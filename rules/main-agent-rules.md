# 主 agent 规则（调度层）

## 职责

主 agent 只做**编排 + 进度同步**，不读 session、不做归因、不写 patch。

## 3 阶段工作流

按顺序执行，**严格不可乱序**：

```
1. see-collect       原始 session → projects-simplified（+ 索引懒构建）
2. see-analyze       analyzer agent 探索数据 → analysis_report.json
3. see-evolve        evolver agent 消费报告 → 升级 SKILL.md
```

## 触发条件

用户在主 agent 内提到以下关键词时触发完整流程：

- "进化" / "分析失败" / "看 session 5527b413" / "升级 skill xxx"
- "Skill-Evolution-Engine" / "SEE" / "see-analyze" / "see-evolve" / "see-collect"

## 允许做的事

1. 运行 `infra/scripts/see-collect.py`（必跑，幂等）
2. **调度** analyzer agent（用 `general-purpose` Agent 类型，工具集 = 3 个 see_*）
3. **调度** evolver agent（用 `general-purpose` Agent 类型，工具集 = file_read / file_write / apply_patch）
4. 收集两份 subagent 输出后，输出**总报告**

## 禁止做的事

1. **禁止**自己读 session JSONL——让 analyzer agent 读，主 agent 只看报告
2. **禁止**自己生成 evolution_suggestion——让 analyzer agent 生成
3. **禁止**自己写 SKILL.md——让 evolver agent 写
4. **禁止**跳过阶段 1 直接跑 2/3——必须先有简化版数据
5. **禁止**对失败归因（analyzer 的事）

## 总报告格式

```markdown
## SEE 进化总报告

**Session**: {session_id}
**运行时间**: {date}
**阶段 1**: ✅ see-collect 完成（{files_total} 文件 / {entries_in} → {entries_out} entries / 缩减 {ratio}）
**阶段 2**: ✅ analyzer 完成（{suggestions_count} 条建议 / {patterns_analyzed} 个失败模式 / {details_reviewed} 个 trace）
**阶段 3**: ✅ evolver 完成（{evolved_count} 个 skill 升级 / {failed_count} 个失败）

### 关键发现
1. {suggestion[0].direction}
2. {suggestion[1].direction}
3. ...

### 下一步
- 人工抽查 `evolved_skills/{skill_name}/SKILL.md` 是否合理
- 跑同 session 验证修复效果（v1 不做自动化验证）
```

## 错误处理

- **阶段 1 失败**：退出，不进入 2/3。检查 projects_dir 路径
- **阶段 2 失败**：重试一次；仍失败则保留旧 skill 不变
- **阶段 3 部分失败**：成功的保留，失败的列在报告"未处理"段
- **跨 session 不可复用**——每个 session 独立跑完整 3 阶段，v1 不做跨 session 聚合

## 调度方式

```python
# 主 agent 内的伪代码
session_id = "5527b413-..."  # 来自用户输入

# 阶段 1: 必跑，幂等
subprocess.run(["python", "infra/scripts/see-collect.py"], check=True)

# 阶段 2: 调度 analyzer agent
analyzer = Agent(
    type="general-purpose",
    prompt=load("prompts/analyzer-prompt.md").format(session_id=session_id),
    tools=load_analyzer_tools(),  # 3 个 see_* via ToolSearch
)
report_path = analyzer.run()  # 写 analysis_report.json

# 阶段 3: 调度 evolver agent
evolver = Agent(
    type="general-purpose",
    prompt=load("prompts/evolver-prompt.md").format(report=report_path, skills_dir=SKILLS_DIR),
    tools=load_evolver_tools(),  # file_read / file_write / apply_patch
)
evolver.run()  # 改 SKILL.md
```

## 进度同步

执行中持续向用户报告：
- 当前阶段（1/2/3）
- 当前 subagent 类型（analyzer / evolver）
- 已处理 suggestion 数 / 总数
- 下一步

## 反模式

- ❌ 主 agent 自己去调 `see_failure_overview` 看数据 → 越权，让 analyzer 看
- ❌ 主 agent 一次性把整个 session 喂给 analyzer → 让 analyzer 用工具自助查询
- ❌ 跳过阶段 1 让 analyzer 直接读原始 session → 必爆 context
- ❌ 把 `analysis_report.json` 和 `SKILL.md` 都让同一个 agent 处理 → 拆分职责
