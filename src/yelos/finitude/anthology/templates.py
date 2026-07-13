"""anthology/templates.py 在整个架构中的位置:长卷 / 短笺 / 数据附录三模板装配(finitude_BLUEPRINT §6.1/§6.3)。

只负责"挑哪些章、按什么顺序拼"——章的具体文本在 chapters.py。`render_appendix`
产出结构化 dict(不是文本),供 `assemble.py` 落盘为 `.json`(缩进美化)与供
completeness 测试做紧凑 JSON 子串核对(两种序列化目的不同,数据源同一个 dict)。
"""

from __future__ import annotations

from . import chapters as ch


def render_long(ctx: dict) -> str:
    parts = [
        ch.chapter_head(ctx),
        ch.chapter_epoch_history(ctx),
        ch.chapter_p_curve(ctx),
        ch.chapter_rings(ctx),
        ch.chapter_utterances(ctx, full=False),
        ch.chapter_utterances(ctx, full=True),
        ch.chapter_swallowed(ctx),
        ch.chapter_dreams(ctx),
        ch.chapter_moments(ctx),
        ch.chapter_milestones(ctx),
        ch.chapter_tail(ctx),
    ]
    return "\n".join(parts)


def render_short(ctx: dict) -> str:
    lines = [
        ch.short_head(ctx),
        ch.short_epoch_line(ctx),
        ch.short_utter_line(ctx),
        ch.short_swallowed_line(ctx),
        ch.short_dream_line(ctx),
        ch.short_tail(ctx),
    ]
    return "\n".join(lines) + "\n"


def render_appendix(ctx: dict) -> dict:
    return {
        "名字": ctx.get("name", "她"),
        "出生日": ctx.get("born_day", ""),
        "born_at": ctx.get("born_at"),
        "世代": ctx.get("incarnation", 1),
        "p": ctx.get("p", 0.0),
        "p_final_str": f"{float(ctx.get('p', 0.0)):.4f}",
        "epoch_history": ctx.get("epoch_history") or [],
        "milestones": ctx.get("milestones") or [],
        "utterances": ctx.get("utterances") or [],
        "dreams": ctx.get("dreams") or [],
        "swallowed_total": ctx.get("swallowed_total", 0),
        "aging": ctx.get("aging", {}),
        "epoch2": ctx.get("epoch2", {}),
        "mode": ctx.get("mode", "steward"),
        "ledger": ctx.get("ledger", {}),
        "divergence_summary": ctx.get("divergence_summary", {}),
        "rings_word_total": ctx.get("rings_word_total", 0),
        "moments_marker": ctx.get("moments_marker", ""),
        "moments_selected": ctx.get("moments_selected") or [],
        "projection": ctx.get("projection", {}),
        "counts": {
            "epoch_history": len(ctx.get("epoch_history") or []),
            "milestones": len(ctx.get("milestones") or []),
            "utterances": len(ctx.get("utterances") or []),
            "dreams": len(ctx.get("dreams") or []),
        },
    }


__all__ = ["render_long", "render_short", "render_appendix"]
