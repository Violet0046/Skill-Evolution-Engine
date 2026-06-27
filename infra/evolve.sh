#!/bin/bash
# Skill进化入口
# 用法: bash infra/evolve.sh <output_dir> <skill_name> [skills_dir] [evolved_skills_dir]
# 注意: skills_dir 默认为当前工作目录下的 skills 文件夹，不是 agent 目录

# 保存当前工作目录
WORK_DIR="$PWD"

# 动态获取agent根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"

OUTPUT_DIR=$1
SKILL_NAME=$2
SKILLS_DIR=${3:-$WORK_DIR/skills}  # 默认使用当前工作目录下的skills
EVOLVED_SKILLS_DIR=${4:-$WORK_DIR/evolved_skills}  # 默认使用当前工作目录下的evolved_skills

if [ -z "$OUTPUT_DIR" ] || [ -z "$SKILL_NAME" ]; then
    echo "错误：请提供output目录和skill名称"
    echo "用法: bash infra/evolve.sh <output_dir> <skill_name> [skills_dir] [evolved_skills_dir]"
    exit 1
fi

# 检查是否错误地指向了 agent 目录
if [[ "$SKILLS_DIR" == *".claude/agents"* ]]; then
    echo "警告：skills目录指向了agent目录，已自动修正为当前工作目录下的skills"
    SKILLS_DIR="$WORK_DIR/skills"
fi

# 将相对路径转换为绝对路径
if [[ ! "$OUTPUT_DIR" = /* ]]; then
    OUTPUT_DIR="$WORK_DIR/$OUTPUT_DIR"
fi
if [[ ! "$SKILLS_DIR" = /* ]]; then
    SKILLS_DIR="$WORK_DIR/$SKILLS_DIR"
fi
if [[ ! "$EVOLVED_SKILLS_DIR" = /* ]]; then
    EVOLVED_SKILLS_DIR="$WORK_DIR/$EVOLVED_SKILLS_DIR"
fi

cd "$AGENT_DIR"

# 检查skill是否存在
SKILLS=$(python infra/scripts/main/get_skills.py "$OUTPUT_DIR" 2>/dev/null | grep "  - " | sed 's/  - //')

if echo "$SKILLS" | grep -q "^${SKILL_NAME}$"; then
    # 生成进化任务
    mkdir -p "$EVOLVED_SKILLS_DIR"
    python infra/scripts/main/evolve.py "$SKILL_NAME" --skills-dir "$SKILLS_DIR" --output-dir "$OUTPUT_DIR" --task-dir "$EVOLVED_SKILLS_DIR"
else
    echo "错误: skill '$SKILL_NAME' 不存在于 output 目录中"
    echo ""
    echo "可用的 skills:"
    python infra/scripts/main/get_skills.py "$OUTPUT_DIR"
    exit 1
fi
