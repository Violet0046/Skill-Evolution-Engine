#!/bin/bash
# 数据采集入口
# 用法: bash infra/collect.sh <sessions_path> [output_dir]

# 动态获取agent根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"

SESSIONS_PATH=$1
OUTPUT_DIR=${2:-$PWD/output}  # 默认输出到当前工作目录

# 检查参数
if [ -z "$SESSIONS_PATH" ]; then
    echo "错误：请提供 sessions 目录路径"
    echo "用法: bash infra/collect.sh <sessions_path> [output_dir]"
    echo "示例: bash infra/collect.sh /path/to/sessions"
    exit 1
fi

# 检查路径是否存在
if [ ! -d "$SESSIONS_PATH" ]; then
    echo "错误：sessions 目录不存在: $SESSIONS_PATH"
    exit 1
fi

# 检查是否有 .jsonl 文件
JSONL_COUNT=$(find "$SESSIONS_PATH" -name "*.jsonl" -type f 2>/dev/null | wc -l)
if [ "$JSONL_COUNT" -eq 0 ]; then
    echo "错误：sessions 目录中没有找到 .jsonl 文件: $SESSIONS_PATH"
    exit 1
fi

echo "找到 $JSONL_COUNT 个 session 文件"

cd "$AGENT_DIR"

# 执行采集
python infra/scripts/main/extract.py "$SESSIONS_PATH" -o "$OUTPUT_DIR"

# 检查执行结果
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "错误：采集脚本执行失败，退出码: $EXIT_CODE"
    exit $EXIT_CODE
fi

# 检查输出目录
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "错误：输出目录未创建: $OUTPUT_DIR"
    exit 1
fi

OUTPUT_COUNT=$(ls -d "$OUTPUT_DIR"/*/ 2>/dev/null | wc -l)
if [ "$OUTPUT_COUNT" -eq 0 ]; then
    echo "警告：输出目录为空，可能没有成功提取任何 session"
    exit 1
fi

echo "采集完成：成功提取 $OUTPUT_COUNT 个 session 到 $OUTPUT_DIR"
