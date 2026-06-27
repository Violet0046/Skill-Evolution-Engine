#!/bin/bash
# 获取skill列表入口
# 用法: bash infra/get_skills.sh <output_dir>

# 保存当前工作目录
WORK_DIR="$PWD"

# 动态获取agent根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"

OUTPUT_DIR=${1:-$WORK_DIR/output}  # 默认使用当前工作目录下的output

if [ ! -d "$OUTPUT_DIR" ]; then
    echo "错误：output目录不存在: $OUTPUT_DIR"
    echo "用法: bash infra/get_skills.sh <output_dir>"
    exit 1
fi

cd "$AGENT_DIR"

# 执行并捕获输出
OUTPUT=$(python infra/scripts/main/get_skills.py "$OUTPUT_DIR")
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "错误：获取skill列表失败"
    exit $EXIT_CODE
fi

echo "$OUTPUT"

# 检查是否有skill
SKILL_COUNT=$(echo "$OUTPUT" | grep -c "^  - ")
if [ "$SKILL_COUNT" -eq 0 ]; then
    echo ""
    echo "警告：未找到任何skill，请检查："
    echo "  1. output目录是否正确: $OUTPUT_DIR"
    echo "  2. session数据是否已采集"
    echo "  3. session中是否包含skill调用记录"
    exit 1
fi
