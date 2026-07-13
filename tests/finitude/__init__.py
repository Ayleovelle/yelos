"""tests/finitude/ 作为子包(与 tests/intrinsic/、tests/shadow/ 同惯例)。

存在的唯一理由:`tests/arbiter/test_concurrency.py`/`test_viz_golden.py` 与
`tests/primal/test_compat_v01.py`(均无 __init__.py,按裸文件名导入)与本目录
同名文件相撞(`import file mismatch`)。加一个 __init__.py 让本目录成为真正的
`finitude` 子包,导入路径变成 `finitude.test_concurrency` 等,不再与裸名冲突。
"""
