#!/usr/bin/env bash
# with-python.sh —— 找到 ≥ 3.8 的 Python 并 exec 剩余参数
# 本项目最低要求 Python 3.8+（PEP 563 future annotations；3.8 是本机已实测可跑）

MIN_MAJOR=3
MIN_MINOR=8

# Python 解释器候选（按从高到低）
CANDIDATES=(python3.13 python3.12 python3.11 python3.10 python3.9 python3.8 python3 python)

# 自动 export infra 到 PYTHONPATH（让 `import core.xxx` 走得到）
# 取脚本所在位置 → .. 算出 infra 目录
_THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_INFRA_DIR="$(cd "$_THIS_DIR/.." && pwd)"
export PYTHONPATH="$_INFRA_DIR${PYTHONPATH:+:$PYTHONPATH}"

for py in "${CANDIDATES[@]}"; do
    if command -v "$py" >/dev/null 2>&1; then
        if "$py" -c "import sys; sys.exit(0 if sys.version_info >= ($MIN_MAJOR, $MIN_MINOR) else 1)" 2>/dev/null; then
            exec "$py" "$@"
        fi
    fi
done

echo "with-python.sh: 需要 Python ${MIN_MAJOR}.${MIN_MINOR}+，但机器上找不到" >&2
echo "尝试的候选: ${CANDIDATES[*]}" >&2
exit 1
