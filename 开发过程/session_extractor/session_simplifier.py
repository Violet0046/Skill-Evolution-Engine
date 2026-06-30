"""v4 collector 向后兼容入口 — 委托到 run.main()。

为保留 v3 的调用习惯（`python3 session_simplifier.py in out`），本文件只做
import + delegate，不再重复 argparse 逻辑。所有 CLI 选项见 run.py。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from run import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())