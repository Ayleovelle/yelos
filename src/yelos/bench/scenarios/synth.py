"""程序化合成器(bench_BLUEPRINT §4.3)——剧本层策略族之二:哈希驱动零随机。

哈希族登记(INTEGRATION_SPEC §3.9 治理规则,``primal/determinism.py``
尚未落地前的临时记账点,W1 后按治理规则迁移过去):

    键 id: ``bench.synth.v1``
    格式: ``f"{seed}|{archetype}|{day}|{slot}"`` → ``blake2b(...).digest()[0]``
    粒度: 每个 (seed, archetype, day, slot 标签) 组合一个确定性字节 0..255
    消费者: 本文件 ``synthesize()`` 的一切"随机"决策(消息数/时刻/强度档/
            poll 覆盖)
    稳定性承诺: 同 seed 同参数永远产生逐字节相同 Scenario(AX-B1 的上游前提)

W1 落地:五原型的形状参数表(``ARCHETYPES``)与两个必需能力——
① 同 seed 同剧本逐字节确定;② 原型间可观测差异(密度/强度直方图不同,
``test_archetype_distinguishable``)。lazy/never poll 修饰器(RE5"懒 agent
可见性损失"义务)本波一并交付。DSL 对抗边角剧本(封存后 submit 等)与
剧本库入库文本留 W4。
"""

from __future__ import annotations

import hashlib

from .schema import Scenario, ScenarioDay, ScenarioEvent

__all__ = ["ARCHETYPES", "synthesize"]

# 强度档权重表(平静/亲昵/高压/退缩,§4.1 语料强度档的 bench 侧简化四档;
# "久别"强度体现在 reunion 原型的 withdraw 权重独占,不另设第五档——档名与
# 权重共同决定可观测差异,而非档名数量)。
ARCHETYPES: dict[str, dict] = {
    "honeymoon": {
        "msgs_min": 8,
        "msgs_max": 14,
        "tier_weights": {"calm": 2, "intimate": 6, "pressure": 1, "withdraw": 1},
        "poll_cadence_min": 90,
    },
    "fatigue": {
        "msgs_min": 2,
        "msgs_max": 5,
        "tier_weights": {"calm": 3, "intimate": 1, "pressure": 3, "withdraw": 3},
        "poll_cadence_min": 180,
    },
    "reunion": {
        "msgs_min": 1,
        "msgs_max": 3,
        "tier_weights": {"calm": 2, "intimate": 2, "pressure": 1, "withdraw": 5},
        "poll_cadence_min": 240,
    },
    "pressure": {
        "msgs_min": 5,
        "msgs_max": 9,
        "tier_weights": {"calm": 1, "intimate": 1, "pressure": 6, "withdraw": 2},
        "poll_cadence_min": 60,
    },
    "silence": {
        "msgs_min": 0,
        "msgs_max": 1,
        "tier_weights": {"calm": 1, "intimate": 1, "pressure": 1, "withdraw": 7},
        "poll_cadence_min": 360,
    },
}

_DAY_START_MIN = 480  # 08:00 本地
_DAY_SPAN_MIN = 840  # 到 22:00 前


def _h(seed: str, archetype: str, day: int, slot: str) -> int:
    """哈希族 ``bench.synth.v1`` 的唯一实现点:首字节驱动,零 random。"""
    key = f"{seed}|{archetype}|{day}|{slot}"
    return hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()[0]


def _pick_tier(
    seed: str, archetype: str, day: int, k: int, weights: dict[str, int]
) -> str:
    total = sum(weights.values())
    r = _h(seed, archetype, day, f"tier{k}") % total
    acc = 0
    for tier, w in weights.items():
        acc += w
        if r < acc:
            return tier
    return next(iter(weights))  # pragma: no cover — 数值上不可达(权重和覆盖全域)


def synthesize(
    archetype: str, days: int, seed: str, poll_discipline: str = "faithful"
) -> Scenario:
    """合成一份 ``days`` 虚拟日的 ``origin="synth"`` 剧本。

    ``poll_discipline``:``"faithful"``(逐条 poll)/``"lazy"``(哈希驱动跳过
    60%)/``"never"``(全不 poll)——总纲 RE5"懒 agent 内在可见性损失"义务。
    """
    if archetype not in ARCHETYPES:
        raise ValueError(f"未知原型:{archetype!r}(可选:{sorted(ARCHETYPES)})")
    if poll_discipline not in ("faithful", "lazy", "never"):
        raise ValueError(f"未知 poll_discipline:{poll_discipline!r}")
    if days < 0:
        raise ValueError("days 不得为负")
    params = ARCHETYPES[archetype]

    scenario_days: list[ScenarioDay] = []
    for day in range(days):
        events: list[ScenarioEvent] = []
        span = params["msgs_max"] - params["msgs_min"] + 1
        n_msgs = params["msgs_min"] + (_h(seed, archetype, day, "n_msgs") % span)
        for k in range(n_msgs):
            at_min = _DAY_START_MIN + (
                _h(seed, archetype, day, f"min{k}") % _DAY_SPAN_MIN
            )
            tier = _pick_tier(seed, archetype, day, k, params["tier_weights"])
            variant = _h(seed, archetype, day, f"txt{k}") % 5
            events.append(
                ScenarioEvent(
                    at_min=at_min,
                    kind="user_msg",
                    payload={"text_key": f"{tier}_{variant:02d}"},
                )
            )

        cadence = params["poll_cadence_min"]
        t = cadence
        idx = 0
        while t < 1440:
            include = poll_discipline != "never"
            if include and poll_discipline == "lazy":
                include = (_h(seed, archetype, day, f"poll{idx}") % 100) >= 60
            if include:
                events.append(ScenarioEvent(at_min=t, kind="impulse_poll", payload={}))
            t += cadence
            idx += 1

        events.sort(key=lambda e: e.at_min)
        scenario_days.append(ScenarioDay(day_index=day, events=tuple(events)))

    return Scenario(
        scenario_id=f"synth-{archetype}-{days}d-{seed}",
        mode="companion",
        days=tuple(scenario_days),
        config_overrides={},
        origin="synth",
    )
