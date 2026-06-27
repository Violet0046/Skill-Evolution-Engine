# Session处理工具

用于处理Claude Code session数据的工具，能够识别entry类型、按时间戳排序、精简字段。

## 项目结构

```
session_extractor/
├── src/                        # 源代码
│   ├── __init__.py
│   ├── classifier.py          # Session条目分类器
│   ├── timestamp.py           # 时间戳解析与排序工具
│   ├── utils.py               # 工具函数（JSONL加载/保存）
│   └── simplifier.py          # Entry精简器
├── tests/                      # 测试
│   ├── __init__.py
│   ├── test_classifier.py     # 分类器测试
│   ├── test_timestamp.py      # 时间戳工具测试
│   ├── test_utils.py          # 工具函数测试
│   └── test_integration.py    # 集成测试
├── test_coverage.py           # 覆盖率测试脚本
├── session_simplifier.py      # 主脚本
├── entry_fields_spec.md       # 字段保留规范文档
├── entry_fields_config.json   # 字段保留配置文件
└── README.md                  # 项目说明
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

### 禁用精简
```bash
python3 session_simplifier.py <input_file> <output_file> --no-simplify
```

示例：
```bash
python3 session_simplifier.py session.jsonl session_simplified.jsonl
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

覆盖率测试：
```bash
python3 test_coverage.py /path/to/sessions/directory
```

## 输出格式

输出文件为JSONL格式，每行是一个JSON对象，包含：
- 原始字段（根据配置精简）
- 新增的`entry_class`字段

## 日志

程序使用Python标准logging模块输出日志，可以通过配置logging级别来控制日志输出。
