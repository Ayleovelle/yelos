"""pytest 引导:把 src-layout 的 ``src/`` 放上 sys.path。

pyproject 的 ``[tool.pytest.ini_options] pythonpath = ["src"]`` 已能让
``import yelos.*`` 生效;此 conftest 是二次保险,使未安装包、或以非 pytest
入口跑测试时,``yelos`` 仍可 import(蓝图 §8 搬运无损第一闸)。
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
