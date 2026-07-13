"""tests/shadow/ 作为子包(与 tests/intrinsic/ 同惯例)。

存在的唯一理由:`tests/arbiter/`(无 __init__.py)与本目录都有
`test_hysteresis.py`/`test_viz_golden.py` 同名文件——pytest 在无 __init__.py
时按裸文件名导入,同名文件跨目录会撞导入缓存(`import file mismatch`)。
加一个 __init__.py 让本目录成为真正的 `tests.shadow` 子包,导入路径变成
`tests.shadow.test_hysteresis`,与 `tests.arbiter.test_hysteresis`(仍是裸名,
若 arbiter 目录后续也补 __init__.py 会变成 `tests.arbiter.test_hysteresis`)
不再冲突。
"""
