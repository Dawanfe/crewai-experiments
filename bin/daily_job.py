#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可执行入口：每日任务编排
"""

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from app.daily_job import main  # type: ignore  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())


