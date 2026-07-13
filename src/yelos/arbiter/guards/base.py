"""guards/base.py 在整个架构中的位置。

AX:A2 前置守卫的类型不变量代码锚点:g: PolicyInput -> Verdict|None,
命中即短路返回 σ=0 的 PASS verdict。组合根装配时对每条守卫跑一遍合成
探针网格并断言"只产 PASS"(fail-fast,§2.1"静态校验"的运行时落地——
Python 无真正静态类型检查手段,这是可执行的最接近物)。
"""

from __future__ import annotations

from typing import Callable, Protocol, Sequence

from ...core.arbiter import ArbiterInput, Verdict
from ..inputs import PolicyInput, PolicyParams
from ..lattice import sigma_of

Guard = Callable[[PolicyInput], "Verdict | None"]
PostFilter = Callable[["Verdict", PolicyInput], "Verdict"]


class GuardProtocol(Protocol):
    def __call__(self, pin: PolicyInput) -> "Verdict | None": ...


class PostFilterProtocol(Protocol):
    def __call__(self, verdict: "Verdict", pin: PolicyInput) -> "Verdict": ...


def _synthetic_probe_grid() -> list[PolicyInput]:
    """装配期自检用的合成探针网格:覆盖各守卫的关键布尔/数值分支。

    不追求穷举(那是 T-P1/T-G2 性质测试的职责),只求触达每条守卫的
    "命中"与"放行"两侧各至少一例,供 fail-fast 断言使用。
    """
    grid: list[PolicyInput] = []
    bool_axes = [
        dict(bound=True, enabled=True, silenced=False, is_self=False),
        dict(bound=False, enabled=True, silenced=False, is_self=False),
        dict(bound=True, enabled=False, silenced=False, is_self=False),
        dict(bound=True, enabled=True, silenced=True, is_self=False),
        dict(bound=True, enabled=True, silenced=False, is_self=True),
    ]
    for axes in bool_axes:
        for has_plain, has_non_plain in ((True, False), (False, False), (True, True)):
            for surface in (
                None,
                {"guard": {"allowed": True}},
                {"guard": {"allowed": False}},
            ):
                for now_ts, last_ts, min_gap in (
                    (1000.0, 0.0, 180),
                    (1000.0, 950.0, 180),
                ):
                    base = ArbiterInput(
                        session_id="probe",
                        day_key="2026-01-01",
                        draft="草稿。",
                        surface=surface,
                        p=0.8,
                        bound=axes["bound"],
                        enabled=axes["enabled"],
                        silenced=axes["silenced"],
                        is_self=axes["is_self"],
                        has_plain=has_plain,
                        has_non_plain=has_non_plain,
                        now_ts=now_ts,
                        last_intervention_ts=last_ts,
                        min_gap_seconds=min_gap,
                    )
                    params = PolicyParams(0.75, 0.55, 0.70, 1.0)
                    grid.append(PolicyInput(base, 0.0, 0, params))
    return grid


def assert_guards_pass_only(guards: Sequence[Guard]) -> None:
    """AX:A2 类型不变量的组合根 fail-fast 断言:守卫只能产 σ=0 的 PASS。"""
    probes = _synthetic_probe_grid()
    for g in guards:
        for pin in probes:
            v = g(pin)
            if v is None:
                continue
            if sigma_of(v) != 0 or v.kind != "PASS":
                name = getattr(g, "__name__", repr(g))
                raise AssertionError(
                    f"guard {name} 违反 A2:返回了 σ>0 的 verdict({v.kind})"
                )


def assert_post_filters_downgrade_only(
    filters: Sequence[PostFilter], sample_pin: PolicyInput
) -> None:
    """AX:A2 后置滤波不变量的轻量自检:对四种 verdict kind 各跑一遍,
    断言 σ(f(v)) <= σ(v)。真正的随机性质测试见 T-G3/T-P3。
    """
    from ...core.arbiter import Verdict as _V

    for kind in ("PASS", "TRIM", "REPLACE", "SWALLOW"):
        v = _V(kind, reason="self_check")
        for f in filters:
            out = f(v, sample_pin)
            if sigma_of(out) > sigma_of(v):
                name = getattr(f, "__name__", repr(f))
                raise AssertionError(f"post filter {name} 违反 A2:σ 被升格")
