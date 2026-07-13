"""anthology/registry.py 在整个架构中的位置:FIELD_REGISTRY(finitude_BLUEPRINT §6.2,T3 的机器体)。

`FIELD_REGISTRY` 是"送别完备性定理"(T3)的构造性证据:每条目静态声明 `path`
(record 或组装上下文 ctx 内的字段路径)、`source`、覆盖的模板集合(非空,CI 断言)、
探针函数(渲染完备性测试用)。`EXCLUDED` 是显式豁免表——瞬态/内态字段,逐条附
豁免理由字符串,不允许"沉默不登记"。

**两层数据视图**:
- 反向测试(T3 反向:record schema 顶层键 ⊆ registry ∪ EXCLUDED)只看**原始
  bindings record** 的顶层键,用 `TOP_LEVEL_COVERED_KEYS()` 判定覆盖。
- 正向测试(T3 正向:满射覆盖)看 `assemble.build_context()` 组装出的**anthology
  上下文 ctx**(合并 record + ledger replay + moments + projection 的读侧视图),
  探针函数吃的是这个 ctx,不是原始 record——原始 record 里没有 `ledger.P 序列`
  这类跨源字段,必须先经组装。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FieldSpec:
    path: str
    source: str  # "bindings" | "ledger" | "primal_snapshot" | "intrinsic_moments"
    templates: frozenset[str]  # ⊆ {"long","short","appendix"},非空
    probe: Callable[[dict], str]

    def __post_init__(self) -> None:
        assert self.templates, f"{self.path}: templates 不得为空(CI 断言)"
        assert self.templates <= {"long", "short", "appendix"}, (
            f"{self.path}: 非法模板名"
        )


def _get(ctx: dict, path: str, default: Any = "") -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part, default)
    return cur


def _str(ctx: dict, path: str, default: Any = "") -> str:
    return str(_get(ctx, path, default))


def _count(ctx: dict, path: str) -> str:
    value = _get(ctx, path, [])
    if isinstance(value, (list, tuple, dict)):
        return str(len(value))
    return "0"


FIELD_REGISTRY: tuple[FieldSpec, ...] = (
    FieldSpec(
        "name",
        "bindings",
        frozenset({"long", "short", "appendix"}),
        lambda c: _str(c, "name", "她"),
    ),
    FieldSpec(
        "born_day",
        "bindings",
        frozenset({"long", "short", "appendix"}),
        lambda c: _str(c, "born_day"),
    ),
    FieldSpec(
        "born_at", "bindings", frozenset({"appendix"}), lambda c: _str(c, "born_at")
    ),
    FieldSpec(
        "incarnation",
        "bindings",
        frozenset({"long", "appendix"}),
        lambda c: _str(c, "incarnation", 1),
    ),
    FieldSpec(
        "p",
        "bindings",
        frozenset({"long", "short", "appendix"}),
        lambda c: f"{float(_get(c, 'p', 0.0)):.4f}",
    ),
    FieldSpec(
        "epoch_history",
        "bindings",
        frozenset({"long", "appendix"}),
        lambda c: _count(c, "epoch_history"),
    ),
    FieldSpec(
        "milestones",
        "bindings",
        frozenset({"long", "appendix"}),
        lambda c: _count(c, "milestones"),
    ),
    FieldSpec(
        "utterances",
        "bindings",
        frozenset({"long", "short", "appendix"}),
        lambda c: _count(c, "utterances"),
    ),
    FieldSpec(
        "dreams",
        "bindings",
        frozenset({"long", "short", "appendix"}),
        lambda c: _count(c, "dreams"),
    ),
    FieldSpec(
        "swallowed_total",
        "bindings",
        frozenset({"long", "short", "appendix"}),
        lambda c: _str(c, "swallowed_total", 0),
    ),
    FieldSpec(
        "aging.model",
        "bindings",
        frozenset({"long", "short", "appendix"}),
        lambda c: _str(c, "aging.model", "linear"),
    ),
    FieldSpec(
        "aging.active_days_settled",
        "bindings",
        frozenset({"long", "appendix"}),
        lambda c: _str(c, "aging.active_days_settled", 0),
    ),
    FieldSpec(
        "aging.params",
        "bindings",
        frozenset({"appendix"}),
        lambda c: json.dumps(
            _get(c, "aging.params", {}), sort_keys=True, ensure_ascii=False
        ),
    ),
    FieldSpec(
        "aging.fast",
        "bindings",
        frozenset({"appendix"}),
        lambda c: _str(c, "aging.fast", 1.0),
    ),
    FieldSpec(
        "epoch2.b_index",
        "bindings",
        frozenset({"appendix"}),
        lambda c: _str(c, "epoch2.b_index", 0),
    ),
    FieldSpec(
        "epoch2.fired_days",
        "bindings",
        frozenset({"appendix"}),
        lambda c: json.dumps(_get(c, "epoch2.fired_days", []), ensure_ascii=False),
    ),
    FieldSpec(
        "mode",
        "bindings",
        frozenset({"appendix"}),
        lambda c: _str(c, "mode", "steward"),
    ),
    FieldSpec(
        "ledger.p_series",
        "ledger",
        frozenset({"long", "appendix"}),
        lambda c: _str(c, "ledger.final_p", ""),
    ),
    FieldSpec(
        "ledger.hi_by_day",
        "ledger",
        frozenset({"appendix"}),
        lambda c: json.dumps(
            _get(c, "ledger.hi_by_day", {}), sort_keys=True, ensure_ascii=False
        ),
    ),
    FieldSpec(
        "ledger.concern_by_day",
        "ledger",
        frozenset({"appendix"}),
        lambda c: json.dumps(
            _get(c, "ledger.concern_by_day", {}), sort_keys=True, ensure_ascii=False
        ),
    ),
    FieldSpec(
        "epoch_divergence",
        "ledger",
        frozenset({"long", "appendix"}),
        lambda c: _str(c, "divergence_summary.count", 0),
    ),
    FieldSpec(
        "epoch_history.pools",
        "primal_snapshot",
        frozenset({"long", "appendix"}),
        lambda c: _str(c, "rings_word_total", 0),
    ),
    FieldSpec(
        "moments_selected",
        "intrinsic_moments",
        frozenset({"long"}),
        lambda c: _str(c, "moments_marker", "她没有留下这样的记录"),
    ),
    FieldSpec(
        "projection.final",
        "ledger",
        frozenset({"long", "short", "appendix"}),
        lambda c: _str(c, "projection.est_remaining_active_days", 0),
    ),
)

# EXCLUDED:record 顶层瞬态/内态字段的豁免表(finitude_BLUEPRINT §6.2 逐字照录)。
EXCLUDED: dict[str, str] = {
    "daily": "日翻转瞬态,其可送别信息已经 ledger settle 行(hi/concern)与 swallowed_total 沉淀",
    "concern_state": "迟滞机内态;concern 史已经 ledger concern 字段沉淀",
    "pending_epoch_notice": "一次性投递旗;纪元史在 epoch_history/milestones",
    "silence_until": "主权瞬态,非她的一生记账",
    "shadow_baseline": "影子日内态;跨日事实归 memory/shadow 模块账面",
    "dream.pending/night_of/count": "投递机内态;梦本体在 dreams",
    "epoch2.deltas/last_psi": "检测器滚动窗;跃迁史在 fired_days(入册)",
    "sealed/seal_kind": "封存态旗标;送别语义已在卷尾章(送别日/终值/沙漏)体现",
}


def _excluded_prefixes() -> set[str]:
    """把 EXCLUDED 的键(可能是 "a.b/c" 这种"共享前缀+多兄弟"简写)展开成顶层前缀集合。

    先按 "/" 拆分出并列的多个子键名(如 "sealed/seal_kind" → "sealed","seal_kind";
    "dream.pending/night_of/count" → "dream.pending","night_of","count"),
    再各自取 "." 前的顶层段。
    """
    tops: set[str] = set()
    for key in EXCLUDED:
        for part in key.split("/"):
            head = part.split(".")[0]
            if head:
                tops.add(head)
    return tops


def top_level_covered_keys() -> set[str]:
    """registry + EXCLUDED 共同覆盖的顶层键集合(T3 反向测试用)。"""
    registered = {spec.path.split(".")[0] for spec in FIELD_REGISTRY}
    return registered | _excluded_prefixes()


def assert_registry_well_formed() -> None:
    """CI 断言:每条目 templates 非空(FieldSpec.__post_init__ 已保证,此处兜底枚举一次)。"""
    for spec in FIELD_REGISTRY:
        assert spec.templates, f"{spec.path} 的 templates 为空"


__all__ = [
    "FieldSpec",
    "FIELD_REGISTRY",
    "EXCLUDED",
    "top_level_covered_keys",
    "assert_registry_well_formed",
]
