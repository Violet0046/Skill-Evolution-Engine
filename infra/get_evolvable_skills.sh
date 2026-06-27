#!/bin/bash
# 获取可进化的skill列表
# 用法: bash infra/get_evolvable_skills.sh <output_dir> [skills_dir]
# 注意: skills_dir 默认为当前工作目录下的 skills 文件夹，不是 agent 目录

# 保存当前工作目录
WORK_DIR="$PWD"

# 动态获取agent根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"

OUTPUT_DIR=${1:-$WORK_DIR/output}
SKILLS_DIR=${2:-$WORK_DIR/skills}  # 默认使用当前工作目录下的 skills

# 检查是否错误地指向了 agent 目录
if [[ "$SKILLS_DIR" == *".claude/agents"* ]]; then
    echo "警告：skills目录指向了agent目录，已自动修正为当前工作目录下的skills"
    SKILLS_DIR="$WORK_DIR/skills"
fi

if [ ! -d "$OUTPUT_DIR" ]; then
    echo "错误：output目录不存在: $OUTPUT_DIR"
    exit 1
fi

if [ ! -d "$SKILLS_DIR" ]; then
    echo "错误：skills目录不存在: $SKILLS_DIR"
    exit 1
fi

cd "$AGENT_DIR"

# 获取所有有失败数据的skill
ANALYZED_SKILLS=$(python infra/scripts/main/get_skills.py "$OUTPUT_DIR" 2>/dev/null | grep "  - " | sed 's/  - //')

if [ -z "$ANALYZED_SKILLS" ]; then
    echo "未找到任何skill数据"
    exit 0
fi

echo "可进化的skill（在skills目录中有定义）："
echo ""

EVOLVABLE_COUNT=0
for skill in $ANALYZED_SKILLS; do
    # 检查skill目录是否存在
    if [ -d "$SKILLS_DIR/$skill" ] && [ -f "$SKILLS_DIR/$skill/SKILL.md" ]; then
        echo "  ✓ $skill"
        EVOLVABLE_COUNT=$((EVOLVABLE_COUNT + 1))
    fi
done

echo ""
echo "共 $EVOLVABLE_COUNT 个skill可进化"

if [ $EVOLVABLE_COUNT -eq 0 ]; then
    echo ""
    echo "提示：skills目录中没有找到与分析数据匹配的SKILL.md文件"
    echo "skills目录: $SKILLS_DIR"
    echo ""
    echo "skills目录中的skill："
    for d in "$SKILLS_DIR"/*/; do
        if [ -d "$d" ] && [ -f "$d/SKILL.md" ]; then
            echo "  - $(basename "$d")"
        fi
    done
fi
