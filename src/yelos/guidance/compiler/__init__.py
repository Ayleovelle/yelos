"""编译器子包:正典解释器(热路径)。差分预编译树(treegen)不在本波交付范围
内(§9 诚实自评:本波把预编译差分测试列为 scope-cut,见模块交付说明)。
"""

from .interpreter import evaluate

__all__ = ["evaluate"]
