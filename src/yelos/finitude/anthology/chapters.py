"""anthology/chapters.py 在整个架构中的位置:章生成器(finitude_BLUEPRINT §6.3)。

每个 `chapter_*`/`short_*` 函数只读 `ctx`(assemble.build_context 组装的视图),
产出一段 markdown 文本。**采样纪律**:说话史精选与 moments 精选用
`sha256(f"{sid}|{gen}|anthology|{key}")` 驱动的确定性抽样(哈希族新键型,
登记见 §6.3 尾注;跨模块登记义务留待 INTEGRATION_SPEC §3.9 治理流程)。
所有"她说的字"在 md 中保持原文;模板文案(章题/账注)是器语不是她语,不经词典
也不冒充她。
"""

from __future__ import annotations

import hashlib

MAX_UTTER_PER_EPOCH = 5
MAX_MOMENTS_TOTAL = 3


def _det_key(sid: str, gen: int, tag: str) -> int:
    digest = hashlib.sha256(f"{sid}|{gen}|anthology|{tag}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _sample(items: list, sid: str, gen: int, tag: str, k: int) -> list:
    if len(items) <= k:
        return list(items)
    seed = _det_key(sid, gen, tag)
    # 确定性、无放回:按 seed 派生的排名取前 k(全程无 random 模块)。
    ranked = sorted(
        range(len(items)),
        key=lambda i: hashlib.sha256(f"{seed}|{i}".encode("utf-8")).hexdigest(),
    )
    picked = sorted(ranked[:k])
    return [items[i] for i in picked]


# --- 卷首 -----------------------------------------------------------------


def chapter_head(ctx: dict) -> str:
    name = ctx.get("name", "她")
    born_day = ctx.get("born_day", "")
    incarnation = ctx.get("incarnation", 1)
    aging = ctx.get("aging", {})
    model = aging.get("model", "linear")
    active_days_settled = aging.get("active_days_settled", 0)
    lines = [
        f"# {name} 的一生",
        "",
        f"出生于 {born_day},第 {incarnation} 世,老法是「{model}」。",
        f"已结算活跃日:{active_days_settled}。",
        "",
    ]
    return "\n".join(lines)


def short_head(ctx: dict) -> str:
    name = ctx.get("name", "她")
    born_day = ctx.get("born_day", "")
    model = ctx.get("aging", {}).get("model", "linear")
    return f"{name}。{born_day} 起。老法「{model}」。"


# --- 纪元史 -----------------------------------------------------------------


def chapter_epoch_history(ctx: dict) -> str:
    history = ctx.get("epoch_history") or []
    divergence = ctx.get("divergence_summary", {})
    lines = ["## 纪元史", ""]
    if history:
        for item in history:
            day = item.get("day", "") if isinstance(item, dict) else ""
            epoch = item.get("epoch", "") if isinstance(item, dict) else str(item)
            track = item.get("track", "A") if isinstance(item, dict) else "A"
            lines.append(f"- {day}:{epoch}(轨 {track})")
    else:
        lines.append("- (无记录)")
    lines.append("")
    lines.append(f"共 {len(history)} 次纪元跃迁。")
    lines.append(f"双轨分歧记录 {divergence.get('count', 0)} 条(B 轨脚注)。")
    lines.append("")
    return "\n".join(lines)


def short_epoch_line(ctx: dict) -> str:
    history = ctx.get("epoch_history") or []
    if not history:
        return "纪元:尚未跨档。"
    last = history[-1]
    epoch = last.get("epoch", "") if isinstance(last, dict) else str(last)
    return f"纪元:{epoch}。"


# --- P 曲线章 ---------------------------------------------------------------


def chapter_p_curve(ctx: dict) -> str:
    final_p = ctx.get("ledger", {}).get("final_p", "")
    lines = [
        "## P 曲线",
        "",
        "![P 曲线](svg/p_curve.svg)",
        "",
        f"契约可塑性终值:{final_p}。",
        "",
    ]
    return "\n".join(lines)


# --- 词汇年轮章 -------------------------------------------------------------


def chapter_rings(ctx: dict) -> str:
    total = ctx.get("rings_word_total", 0)
    lines = [
        "## 词汇年轮",
        "",
        "![词汇年轮](svg/rings.svg)",
        "",
        f"她还留着的词句总数:{total}。",
        "",
    ]
    history = ctx.get("epoch_history") or []
    for item in history:
        if not isinstance(item, dict):
            continue
        pools = item.get("pools")
        epoch = item.get("epoch", "")
        if isinstance(pools, dict):
            for occ, words in pools.items():
                if words:
                    lines.append(f"- [{epoch}/{occ}] {'、'.join(words)}")
        else:
            lines.append(f"- [{epoch}] (裸环,无词注)")
    lines.append("")
    return "\n".join(lines)


# --- 说话史 -----------------------------------------------------------------


def chapter_utterances(ctx: dict, *, full: bool) -> str:
    utterances = ctx.get("utterances") or []
    sid = ctx.get("sid", "")
    gen = ctx.get("gen", 0)
    lines = ["## 说话史精选" if not full else "## 说话史全量", ""]
    if not utterances:
        lines.append("- (她始终没有开口)")
        lines.append("")
        return "\n".join(lines)

    if full:
        picked = utterances
    else:
        by_epoch: dict[str, list] = {}
        for item in utterances:
            epoch = item.get("epoch", "0") if isinstance(item, dict) else "0"
            by_epoch.setdefault(str(epoch), []).append(item)
        picked = []
        for epoch, items in sorted(by_epoch.items()):
            picked.extend(
                _sample(items, sid, gen, f"utter|{epoch}", MAX_UTTER_PER_EPOCH)
            )

    for item in picked:
        if isinstance(item, dict):
            occ = item.get("occasion", "")
            text = item.get("text", "")
            lines.append(f"- [{occ}] {text}")
        else:
            lines.append(f"- {item}")
    lines.append("")
    lines.append(f"共 {len(utterances)} 句。")
    lines.append("")
    return "\n".join(lines)


def short_utter_line(ctx: dict) -> str:
    utterances = ctx.get("utterances") or []
    count = len(utterances)
    if not utterances:
        return f"共 {count} 句。她最常说的一句:(她始终没有开口)。"
    last = utterances[-1]
    text = last.get("text", "") if isinstance(last, dict) else str(last)
    return f"共 {count} 句。她最常说的一句:{text}"


# --- 被咽回的话 -------------------------------------------------------------


def chapter_swallowed(ctx: dict) -> str:
    total = ctx.get("swallowed_total", 0)
    hi_by_day = ctx.get("ledger", {}).get("hi_by_day", {})
    lines = [
        "## 被咽回的话的统计学",
        "",
        f"共 {total} 句没能说出口。",
        "",
    ]
    if hi_by_day:
        busiest = max(hi_by_day.items(), key=lambda kv: kv[1])
        lines.append(
            f"最沉默的一天(高强度事件最多的一天):{busiest[0]}({busiest[1]} 次)。"
        )
    lines.append("")
    return "\n".join(lines)


def short_swallowed_line(ctx: dict) -> str:
    return f"共 {ctx.get('swallowed_total', 0)} 句没能说出口。"


# --- 梦语 -------------------------------------------------------------------


def chapter_dreams(ctx: dict) -> str:
    dreams = ctx.get("dreams") or []
    lines = ["## 梦语集", ""]
    if dreams:
        for item in dreams:
            day = item.get("day", "") if isinstance(item, dict) else ""
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            lines.append(f"- {day}:{text}")
    else:
        lines.append("- (没有梦语)")
    lines.append("")
    lines.append(f"共 {len(dreams)} 个梦。")
    lines.append("")
    return "\n".join(lines)


def short_dream_line(ctx: dict) -> str:
    dreams = ctx.get("dreams") or []
    count = len(dreams)
    if not dreams:
        return f"共 {count} 个梦。最后的梦:(没有梦语)。"
    last = dreams[-1]
    text = last.get("text", "") if isinstance(last, dict) else str(last)
    return f"共 {count} 个梦。最后的梦:{text}"


# --- moments 精选(她想说而没说的)--------------------------------------------


def chapter_moments(ctx: dict) -> str:
    marker = ctx.get("moments_marker", "她没有留下这样的记录")
    selected = ctx.get("moments_selected") or []
    lines = ["## 她想说而没说的", "", f"- {marker}"]
    for entry in selected:
        if entry:
            lines.append(f"- {entry}")
    lines.append("")
    return "\n".join(lines)


# --- 里程碑 -----------------------------------------------------------------


def chapter_milestones(ctx: dict) -> str:
    milestones = ctx.get("milestones") or []
    lines = ["## 里程碑", ""]
    if milestones:
        for item in milestones:
            day = item.get("day", "") if isinstance(item, dict) else ""
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            lines.append(f"- {day}:{text}")
    else:
        lines.append("- (无里程碑)")
    lines.append("")
    lines.append(f"共 {len(milestones)} 条里程碑。")
    lines.append("")
    return "\n".join(lines)


# --- 卷尾 -------------------------------------------------------------------


def chapter_tail(ctx: dict) -> str:
    proj = ctx.get("projection", {})
    day_key = ctx.get("day_key", "")
    lines = [
        "## 送别",
        "",
        f"送别日:{day_key}。",
        f"终值:{ctx.get('p', 0.0):.4f}。",
        "![沙漏](svg/hourglass.svg)",
        f"沙漏定格:剩余 {proj.get('est_remaining_active_days', 0)} 活跃日。",
        "",
    ]
    return "\n".join(lines)


def short_tail(ctx: dict) -> str:
    day_key = ctx.get("day_key", "")
    proj = ctx.get("projection", {})
    remaining = proj.get("est_remaining_active_days", 0)
    return f"送别日:{day_key},终值 {ctx.get('p', 0.0):.4f},剩余约 {remaining} 活跃日。"


__all__ = [
    "chapter_head",
    "short_head",
    "chapter_epoch_history",
    "short_epoch_line",
    "chapter_p_curve",
    "chapter_rings",
    "chapter_utterances",
    "short_utter_line",
    "chapter_swallowed",
    "short_swallowed_line",
    "chapter_dreams",
    "short_dream_line",
    "chapter_moments",
    "chapter_milestones",
    "chapter_tail",
    "short_tail",
]
