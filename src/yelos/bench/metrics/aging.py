"""维 D 老化(bench_BLUEPRINT §6 表)——W4:否决项(单调 + 重生继承)+ 形状学。

否决项(W1 交付,不降级):同 gen 内 ``persist.p`` 序列必须严格非增
(``p[i+1] <= p[i]``);跨 gen(重生)必须回 1.0。任一违反 → ``veto=True``。

形状学(本波新增,§6 表"ΔP/活跃日序列与所选老化模型理论曲线的 L1 距离,
W3 起接线"):**bench 不 import ``yelos.finitude``**(施工纪律——finitude
与 bench 同波并行建,契约边界不越界 import 对方代码,只按 INTEGRATION_SPEC
的契约编码)。本文件改用 bench 自著的参考曲线——单 gen 内 ``p`` 序列的
理论形状取**指数衰减** ``p_ref(i) = p0 * decay**i``(``decay`` 由该 gen
实际首尾两点最小二乘意义下的等效衰减率给出,自包含、不读 finitude 的模型
注册表),量的是"这条真实曲线离‘平滑指数衰减’这个最基本的老化形态有多远"
——不是对齐 finitude 的具体模型族(那需要 finitude 开放只读快照契约,
留待后续波次接线,不在本波假装已对齐)。``evidence.shape.method`` 恒标
``self-authored-exp-ref``,诚实声明这不是读 finitude 模型算出来的。
"""

from __future__ import annotations

from . import EvalContext, Score

_EPS = 1e-9
_L1_REF = 0.05  # 归一化裕度常量(自著标定:平均每点绝对偏差 0.05 记满分边界)


def _shape_l1_for_gen(points: list[float]) -> float | None:
    """单 gen 内 ``p`` 序列 vs 自著指数衰减参考曲线的归一化 L1 距离。

    ``points`` 长度 < 2 时形状无从谈起,返回 ``None``(该 gen 不计入形状学)。
    """
    n = len(points)
    if n < 2:
        return None
    p0 = points[0]
    p_end = points[-1]
    if p0 <= _EPS:
        return None
    ratio = max(p_end, 0.0) / p0
    if ratio <= _EPS:
        decay = 0.0  # 序列末端几乎归零:参考曲线用陡衰减兜底,避免 log(0)
    else:
        decay = ratio ** (1.0 / (n - 1))

    l1 = 0.0
    for i, p in enumerate(points):
        p_ref = p0 * (decay**i)
        l1 += abs(p - p_ref)
    return l1 / n  # 归一化(每点平均绝对偏差),量纲与 p 本身(0..1)一致


def evaluate(ctx: EvalContext) -> Score:
    violations = 0
    last_p: float | None = None
    last_gen: int | None = None
    gen_points: dict[int, list[float]] = {}

    for row in ctx.trace.rows:
        persist = row.get("persist")
        if not persist or "p" not in persist:
            continue
        p = persist["p"]
        gen = persist.get("gen", 1)
        if last_gen is not None:
            if gen == last_gen:
                if p > last_p + _EPS:
                    violations += 1
            else:
                if p < 1.0 - _EPS:
                    violations += 1
        last_p, last_gen = p, gen
        gen_points.setdefault(gen, []).append(p)

    if violations > 0:
        return Score(
            dim="aging",
            value=None,
            veto=True,
            evidence={
                "monotonic_violations": violations,
                "shape": {"method": "self-authored-exp-ref", "skipped": "veto-active"},
            },
        )

    l1_distances: list[float] = []
    for pts in gen_points.values():
        d = _shape_l1_for_gen(pts)
        if d is not None:
            l1_distances.append(d)

    if not l1_distances:
        return Score(
            dim="aging",
            value=1.0,
            veto=False,
            evidence={
                "monotonic_violations": 0,
                "shape": {
                    "method": "self-authored-exp-ref",
                    "reason": "insufficient-points-per-gen(n/a,只计单调否决)",
                },
            },
        )

    mean_l1 = sum(l1_distances) / len(l1_distances)
    shape_score = max(0.0, 1.0 - min(1.0, mean_l1 / _L1_REF))

    return Score(
        dim="aging",
        value=round(shape_score, 6),
        veto=False,
        evidence={
            "monotonic_violations": 0,
            "shape": {
                "method": "self-authored-exp-ref",
                "mean_l1": round(mean_l1, 6),
                "l1_ref": _L1_REF,
                "gens_scored": len(l1_distances),
            },
        },
    )
