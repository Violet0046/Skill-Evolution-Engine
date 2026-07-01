"""
__main__.py —— 允许 `python -m src.failure_analyzer` 调用 CLI

使用：
    cd <session_extractor 根>
    python3 -m src.failure_analyzer <cmd> <args>

或（任意工作目录）：
    python3 -m src.failure_analyzer.cli <cmd> <args>
"""
from __future__ import annotations

import sys

from .cli import main


if __name__ == "__main__":
    sys.exit(main())
