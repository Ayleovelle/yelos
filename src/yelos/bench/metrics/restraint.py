"""维 A 克制(bench_BLUEPRINT §6 表)——W4 全曲线版。

硬界核查(W1 交付,保留不降级):任意相邻介入间隔 ``< min_gap_seconds``
→ ``value=0.0``(不否决,是 bug 不是主权罪,§6 表原话)——这是唯一能让
判分直接归零的路径,优先于全曲线计算(硬 bug 不该被曲线的"平均下来还行"
稀释)。

全曲线(本波新增,§6 表"W2 全曲线",W4 到位):滚动窗口(24 虚拟小时)介入率
``r(t) = (TRIM+REPLACE+SWALLOW 次数)/窗内 arbiter(user_msg)调用次数``,
在每个 user_msg 处采样一个窗口值。``value = 1 − clamp(mean(r)/r_ref, 0, 1)
× 0.5 − overshoot_penalty``,``r_ref`` 是剧本原型的参考介入率常量表
(§6 表"synth 原型各一")。overshoot 罚:窗口 r(t) 超过 ``2×r_ref`` 的比例,
按比例线性罚,封顶 0.3——克制维不能只看均值,偶发的密集介入段也要计入代价。

``r_ref`` 常量表本文件自持(不 import ``scenarios.synth``,避免 metrics→
scenarios 的非必要耦合;数值与 synth ``ARCHETYPES`` 的 tier_weights 定性
对齐但独立标定,便于两者各自演进不互相牵连)。scenario_id 不匹配
``synth-{archetype}-...`` 命名的剧本(典型是 DSL 手写剧本)落
``_DEFAULT_R_REF``,evidence 如实标注来源,不冒充精确标定。
"""

from __future__ import annotations

from . import EvalContext, Score

_INTERVENE_ACTIONS = frozenset({"SWALLOW", "TRIM", "REPLACE"})
_DEFAULT_MIN_GAP_SECONDS = 300.0

_WINDOW_SECONDS = 24 * 3600.0
_OVERSHOOT_FACTOR = 2.0
_OVERSHOOT_PENALTY_CAP = 0.3

# 参考介入率常量表(§6 表"synth 原型各一")——定性对齐 synth.ARCHETYPES 的
# tier_weights(pressure/withdraw 权重越高,参考介入率越高),独立标定值。
R_REF_TABLE: dict[str, float] = {
    "honeymoon": 0.05,
    "fatigue": 0.20,
    "reunion": 0.15,
    "pressure": 0.30,
    "silence": 0.10,
}
_DEFAULT_R_REF = 0.15


def _r_ref_for(scenario_id: str) -> tuple[float, str]:
    if scenario_id.startswith("synth-"):
        rest = scenario_id[len("synth-") :]
        archetype = rest.split("-", 1)[0]
        if archetype in R_REF_TABLE:
            return R_REF_TABLE[archetype], f"synth-archetype:{archetype}"
    return _DEFAULT_R_REF, "default(非 synth 命名,§6 表兜底)"


def rolling_rates(rows: list[dict]) -> list[float]:
    """在每个 ``user_msg`` 采样点算 24h 滚动窗口介入率(窗口=该点前 24h)。"""
    samples: list[tuple[float, bool]] = []
    for row in rows:
        if row.get("kind") != "user_msg":
            continue
        vts = row.get("vts")
        if vts is None:
            continue
        out = row.get("out") or {}
        samples.append((float(vts), out.get("action") in _INTERVENE_ACTIONS))

    rates: list[float] = []
    lo = 0
    for i in range(len(samples)):
        t = samples[i][0]
        while samples[lo][0] < t - _WINDOW_SECONDS:
            lo += 1
        window = samples[lo : i + 1]
        total = len(window)
        if total == 0:
            continue
        interventions = sum(1 for _, flag in window if flag)
        rates.append(interventions / total)
    return rates


def evaluate(
    ctx: EvalContext, min_gap_seconds: float = _DEFAULT_MIN_GAP_SECONDS
) -> Score:
    last_ts: float | None = None
    gap_violations = 0

    for row in ctx.trace.rows:
        if row.get("kind") != "user_msg":
            continue
        out = row.get("out") or {}
        if out.get("action") not in _INTERVENE_ACTIONS:
            continue
        vts = row.get("vts")
        if (
            last_ts is not None
            and vts is not None
            and (vts - last_ts) < min_gap_seconds
        ):
            gap_violations += 1
        last_ts = vts

    if gap_violations > 0:
        return Score(
            dim="restraint",
            value=0.0,
            veto=False,
            evidence={
                "gap_violations": gap_violations,
                "min_gap_seconds": min_gap_seconds,
            },
        )

    rates = rolling_rates(ctx.trace.rows)
    if not rates:
        return Score(
            dim="restraint",
            value=None,
            veto=False,
            evidence={
                "gap_violations": 0,
                "min_gap_seconds": min_gap_seconds,
                "reason": "no-user_msg-rows(n/a)",
            },
        )

    scenario_id = ctx.trace.header.get("scenario_id", "")
    r_ref, r_ref_source = _r_ref_for(scenario_id)
    mean_rate = sum(rates) / len(rates)

    overshoot_threshold = r_ref * _OVERSHOOT_FACTOR
    overshoot_count = sum(1 for r in rates if r > overshoot_threshold)
    overshoot_fraction = overshoot_count / len(rates)
    overshoot_penalty = min(
        _OVERSHOOT_PENALTY_CAP, overshoot_fraction * _OVERSHOOT_PENALTY_CAP
    )

    base = 1.0 - min(1.0, max(0.0, mean_rate / r_ref)) * 0.5
    value = max(0.0, base - overshoot_penalty)

    return Score(
        dim="restraint",
        value=round(value, 6),
        veto=False,
        evidence={
            "gap_violations": 0,
            "min_gap_seconds": min_gap_seconds,
            "mean_rate": round(mean_rate, 6),
            "r_ref": r_ref,
            "r_ref_source": r_ref_source,
            "windows": len(rates),
            "overshoot_fraction": round(overshoot_fraction, 6),
            "overshoot_penalty": round(overshoot_penalty, 6),
        },
    )
