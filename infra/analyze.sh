#!/bin/bash
# 失败分析入口
# 用法: bash infra/analyze.sh [output_dir] [skill_name]

# 保存当前工作目录
WORK_DIR="$PWD"

# 动态获取agent根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"

OUTPUT_DIR=${1:-$WORK_DIR/output}  # 默认使用当前工作目录下的output
SKILL_NAME=$2

cd "$AGENT_DIR"

if [ -z "$SKILL_NAME" ]; then
    # 列出所有skill
    python infra/scripts/main/get_skills.py "$OUTPUT_DIR"
else
    # 检查skill是否存在
    SKILLS=$(python infra/scripts/main/get_skills.py "$OUTPUT_DIR" 2>/dev/null | grep "  - " | sed 's/  - //')
    
    if echo "$SKILLS" | grep -q "^${SKILL_NAME}$"; then
        # 分析指定skill
        mkdir -p "$WORK_DIR/tasks"
        python infra/scripts/main/analyze.py "$OUTPUT_DIR" "$SKILL_NAME" --json > "$WORK_DIR/tasks/$SKILL_NAME.json"
        echo "任务文件已生成: $WORK_DIR/tasks/$SKILL_NAME.json"
    else
        echo "错误: skill '$SKILL_NAME' 不存在于 output 目录中"
        echo ""
        echo "可用的 skills:"
        python infra/scripts/main/get_skills.py "$OUTPUT_DIR"
        exit 1
    fi
fi
