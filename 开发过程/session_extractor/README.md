# Session处理工具（v4）

用于处理 Claude Code session 数据的工具，能够识别 entry 类型、按时间戳排序、精简字段，并产出**分层结构化证据包**（含 5 类 detector 硬约束事件）。

## v4 与 v3 关键差异

| 项 | v3 | v4 |
|---|---|---|
| truncate_enabled 默认 | false | **true** |
| detector 层 | 无 | **5 类**（state_machine / gate / review_contract / user_confirmation / symlink） |
| agent_spec 插件化 | 无 | **specs/*.yaml** |
| 输出格式 | header + NDJSON（v3 第 1 行） | header (含 v4 扩展) + NDJSON（trace 字段集与 v3 一致） |
| CLI 副作用 | 修改 entry_fields_config.json | **无副作用**（新增 `--write-config-defaults` 显式写回） |

## 项目结构

```
session_extractor/
├── src/                              # 源代码
│   ├── __init__.py
│   ├── classifier.py                 # Session条目分类器（v3 复用）
│   ├── timestamp.py                  # 时间戳解析与排序工具（v3 复用）
│   ├── utils.py                      # 工具函数（JSONL加载/保存，v3 复用）
│   ├── simplifier.py                 # Entry精简器（v3 复用）
│   ├── models.py                     # v4 数据模型（dataclass）
│   ├── pipeline.py                   # v4 主流程编排
│   ├── spec_loader.py                # agent_spec YAML 加载器
│   └── detectors/                    # v4 detector 插件
│       ├── base.py                   # Detector 抽象基类 + @register
│       ├── state_machine.py          # phase 状态轨迹
│       ├── gate.py                   # *-gate.mjs 拒答
│       ├── review_contract.py        # review-agent 契约
│       ├── user_confirmation.py      # AskUserQuestion / auto_confirm / interrupted
│       └── symlink.py                # cwd 物理源判定
├── specs/                            # agent_spec YAML 雏形
│   ├── spec.yaml                     # phases[]
│   ├── hooks.yaml                    # gates[]
│   ├── subagents.yaml                # review-agent 契约
│   └── constraints.yaml              # 五层硬约束声明
├── tests/                            # 测试
│   ├── test_classifier.py            # v3 复用
│   ├── test_simplifier.py            # v3 复用（含 truncate 默认 ON 测试）
│   ├── test_timestamp.py             # v3 复用
│   ├── test_utils.py                 # v3 复用
│   ├── test_integration.py           # 跨平台改造（Path(__file__).parent）
│   ├── test_models.py                # v4 数据模型
│   ├── test_pipeline.py              # 伪样本 e2e
│   ├── test_pipeline_real.py         # 真实样本 e2e（RUN_REAL=1）
│   ├── test_v3_compat.py             # v3 trace 字段兼容回归
│   ├── test_spec_loader.py           # spec_loader 单测
│   ├── test_detector_state_machine.py
│   ├── test_detector_gate.py
│   ├── test_detector_review_contract.py
│   ├── test_detector_user_confirmation.py
│   └── test_detector_symlink.py
├── test_coverage.py                  # 覆盖率测试脚本
├── session_simplifier.py             # 主脚本（v4 薄壳）
├── entry_fields_spec.md              # 字段保留规范文档（v4）
├── entry_fields_config.json          # 字段保留配置文件（v4：truncate_enabled=true）
├── requirements.txt                  # pyyaml>=6.0
└── README.md                         # 本文件
```

## 分类规则

根据entry的`type`字段和`message.content`中的`type`字段进行分类：

### user类型
- **user_command**：`message.content`包含`<>`且尖括号里面有`command`
- **user_input**：`message.content`中的type为`text`，或content为普通字符串

### assistant类型
- **ai_text**：`message.content`中的type为`text`
- **ai_tool_call**：`message.content`中的type为`tool_use`

### 其他类型
- **attachment**：附件类型
- **system**：系统事件
- **queue-operation**：队列操作
- **last-prompt**：最后提示
- **file-history-snapshot**：文件快照
- **permission-mode**：权限模式
- **ai-title**：AI标题

## 使用方法

### 基本用法
```bash
python3 session_simplifier.py <input_file> <output_file>
```

示例：
```bash
python3 session_simplifier.py 1b4c0c37-23cc-4e75-9eb9-125629d9d274.jsonl out_v4.jsonl
```

输出第 1 行 JSON header（含 v3 兼容键 + v4 扩展键 `schema_version=4.0` / `state_machine` / `constraint_events` 等），第 2+ 行 NDJSON trace（字段集与 v3 一致）。

### 高级用法

```bash
# 传 agent_spec 目录（detector 由 spec 驱动）
python3 session_simplifier.py in.jsonl out.jsonl --spec-dir specs/

# 跳过所有 detector（v3 行为）
python3 session_simplifier.py in.jsonl out.jsonl --no-detectors

# 仅启用指定 detector
python3 session_simplifier.py in.jsonl out.jsonl --detector state_machine --detector gate

# 显式关闭 truncation（v3 默认行为）
python3 session_simplifier.py in.jsonl out.jsonl --no-truncate

# 显式启用 truncation（与 v4 默认一致；冗余）
python3 session_simplifier.py in.jsonl out.jsonl --truncate

# 禁用字段精简（保留全部字段）
python3 session_simplifier.py in.jsonl out.jsonl --no-simplify

# 一次性把 truncate_enabled=true 写回 entry_fields_config.json
python3 session_simplifier.py --write-config-defaults

# 静默模式
python3 session_simplifier.py in.jsonl out.jsonl --quiet
```

### 完整 CLI

```
session_simplifier.py [-h] [--no-simplify] [--truncate] [--no-truncate]
                      [--no-detectors] [--detector DETECTOR]
                      [--spec-dir SPEC_DIR] [--write-config-defaults]
                      [--quiet]
                      input_file output_file
```

## 字段精简

根据 `entry_fields_config.json` 配置文件，自动精简entry字段：

- **必须保留**：对于理解agent行为和决策至关重要的字段
- **建议保留**：对于分析和改进有帮助的字段
- **可选保留**：对于完整性有用但不关键的字段
- **不保留**：对于进化目标无价值的字段

详见 `entry_fields_spec.md` 文档。

## 运行测试

单元测试：
```bash
python3 -m unittest discover -v tests/
```

真实样本端到端测试（默认 skip，需显式启用）：
```bash
RUN_REAL=1 python3 -m unittest tests.test_pipeline_real -v
```

覆盖率测试：
```bash
python3 test_coverage.py /path/to/sessions/directory
```

## 输出格式（v4 分层结构化证据包）

**第 1 行 = header JSON**，同时含 v3 兼容键与 v4 扩展键：

```json
{
  "schema_version": "4.0",
  "session": {"sessionId": "...", "version": "...", ...},
  "cwd_changes": 0,
  "trace": [...],   // 第 2+ 行 NDJSON（v3 兼容字段集）
  "state_machine": {"phases": [...], "transitions": [...], "unexpected_exits": []},
  "constraint_events": [{"kind": "gate_rejected|review_contract|...", "evidence_ref": "uuid"}],
  "user_feedback": [{"uuid": "...", "text": "...", "timestamp": "..."}],
  "execution_pattern": {"step_counts": {...}, "tool_distribution": {...}, "phase_durations": {...}},
  "detector_meta": {"enabled": [...], "spec_loaded": false, "truncate_enabled": true}
}
```

**第 2+ 行 = NDJSON trace entries**，字段集与 v3 完全一致：
- 必需字段：`uuid, parentUuid, timestamp, entry_class` + 各 entry_class 的 required 字段
- v3 consumer 仍可读（schema_version=4.0 时按 v4 处理，否则按 v3）

详见 [entry_fields_spec.md](entry_fields_spec.md) §11。

## 日志

程序使用Python标准logging模块输出日志，可以通过配置logging级别来控制日志输出。`--quiet` 启用 INFO 级日志输出。
