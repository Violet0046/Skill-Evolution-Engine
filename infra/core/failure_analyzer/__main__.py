"""
__main__.py —— 允许 `python -m core.failure_analyzer` 调用 CLI

使用：
    cd <Skill-Evolution-Engine 根>
    PYTHONPATH=infra python3 -m core.failure_analyzer <cmd> <args>

或（任意工作目录）：
    PYTHONPATH=infra python3 -m core.failure_analyzer.cli <cmd> <args>
"""
from __future__ import annotations

import sys

from .cli import main


if __name__ == "__main__":
    sys.exit(main())
