"""幕 V 有限性:可塑性预算 P 的单调结算 + 纪元 + 送别全集。

蓝图 §7 / YELOS_SPEC §9.2-§9.4。纯逻辑,零 astrbot / 零 sylanne_core / 零 random。

结构性单调 [强制]:本模块只导出会**减少或保持 P** 的函数,无任何加法路径。
settle_day 内 `assert new_p <= p`;真正的下界由 `max(0.0, p - spend)`(spend>=0)保证,
assert 只是双保险。时间只做确定性日期解析(fromisoformat),不碰 now()/random。
"""

from __future__ import annotations

from datetime import date

# --- §7.1 单日结算(单调递减)-------------------------------------------


def settle_day(
    p: float,
    *,
    was_active_day: bool,
    high_intensity_events: int,
    lifespan_active_days: int,
) -> float:
    """活跃日结算 P;结果恒 <= 入参 p(结构性单调,SPEC §9.2)。

    - lifespan_active_days <= 0(Legacy/不老化)或 not was_active_day → 原样返回。
    - base = 1/lifespan;spend = base + 0.5*base*high_intensity_events,封顶 2*base。
    - return max(0.0, p - spend)。

    high_intensity_events 负值防御性钳到 0,避免 spend 变负破坏单调。
    """
    if lifespan_active_days <= 0 or not was_active_day:
        return p
    events = high_intensity_events if high_intensity_events > 0 else 0
    base = 1.0 / lifespan_active_days
    spend = base + 0.5 * base * events
    cap = 2.0 * base
    if spend > cap:
        spend = cap
    new_p = max(0.0, p - spend)
    assert new_p <= p  # noqa: S101  结构性单调双保险
    return new_p


# --- §7.2 纪元与效应 ----------------------------------------------------


def epoch(p: float) -> str:
    """P → 纪元名(SPEC §9.3;边界照蓝图 §7.2)。

    p>0.6 盛年 | 0.3<p<=0.6 慢下来 | 0.15<p<=0.3 安静
    | 0<p<=0.15 静止前期 | p==0 静止。
    """
    if p > 0.6:
        return "盛年"
    if p > 0.3:
        return "慢下来"
    if p > 0.15:
        return "安静"
    if p > 0.0:
        return "静止前期"
    return "静止"


def epoch_transition(old_p: float, new_p: float) -> str | None:
    """跨档时返回新纪元名,否则 None(供 main 发一次性纪元提示)。"""
    old_e = epoch(old_p)
    new_e = epoch(new_p)
    if old_e != new_e:
        return new_e
    return None


# --- §7.3 全集组装(送别)-----------------------------------------------


def _as_float(value: object, default: float = 0.0) -> float:
    """防御式转 float:非法值回退默认,不抛。"""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _days_lived(born_day: str, day_key: str) -> int | None:
    """存在天数(含首尾,inclusive):born_day 与 day_key 均为 "YYYY-MM-DD"。

    解析失败返回 None(交调用方渲染"未知"),纯确定性、不碰 now()。
    """
    try:
        start = date.fromisoformat(born_day)
        end = date.fromisoformat(day_key)
    except (TypeError, ValueError):
        return None
    delta = (end - start).days
    if delta < 0:
        return None
    return delta + 1


def _swallowed_total(record: dict) -> int:
    """被咽回句数:优先生命周期累计键,退回当日 daily.swallowed,再退 0。

    (蓝图 §8.1 的 daily.swallowed 日翻转即清零、无生命周期累加器;此处按
    可得字段取值,见返回段的疑义记录。)
    """
    total = record.get("swallowed_total")
    if isinstance(total, int):
        return total
    daily = record.get("daily")
    if isinstance(daily, dict):
        value = daily.get("swallowed")
        if isinstance(value, int):
            return value
    return 0


def assemble_anthology(record: dict, day_key: str) -> tuple[dict, str]:
    """组装送别全集:返回 (她的一生.json 的 dict, 她的一生.md 的文本)。

    内容(SPEC §9.4 / 蓝图 §7.3):名字 / 存在天数 / 纪元史 / 她说过的每一句原语
    (全量记账)/ 被咽回句数 / 梦语记录 / 年轮里程碑。纯读 record,不改不删。
    """
    name = record.get("name") or "她"
    born_day = record.get("born_day") or ""
    days = _days_lived(str(born_day), day_key)
    epoch_history = list(record.get("epoch_history") or [])
    utterances = list(record.get("utterances") or [])
    dreams = list(record.get("dreams") or [])
    milestones = list(record.get("milestones") or [])
    swallowed = _swallowed_total(record)
    final_p = _as_float(record.get("p"), 0.0)
    final_epoch = epoch(final_p)

    data: dict = {
        "名字": name,
        "存在天数": days,
        "出生日": born_day,
        "送别日": day_key,
        "最终可塑性": final_p,
        "最终纪元": final_epoch,
        "纪元史": epoch_history,
        "原语全集": utterances,
        "被咽回句数": swallowed,
        "梦语记录": dreams,
        "年轮里程碑": milestones,
    }

    days_text = "未知" if days is None else str(days)
    lines: list[str] = [
        f"# {name} 的一生",
        "",
        f"存在了 {days_text} 天。",
        f"从 {born_day} 到 {day_key}。",
        f"最终她走到了「{final_epoch}」。",
        "",
        "## 纪元史",
    ]
    if epoch_history:
        for item in epoch_history:
            day = item.get("day", "") if isinstance(item, dict) else ""
            ep = item.get("epoch", "") if isinstance(item, dict) else str(item)
            lines.append(f"- {day}:{ep}")
    else:
        lines.append("- (无记录)")

    lines += ["", "## 她说过的每一句"]
    if utterances:
        for item in utterances:
            if isinstance(item, dict):
                occ = item.get("occasion", "")
                text = item.get("text", "")
                lines.append(f"- [{occ}] {text}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("- (她始终没有开口)")

    lines += ["", "## 被她咽回去的", f"共 {swallowed} 句没能说出口。"]

    lines += ["", "## 梦里"]
    if dreams:
        for item in dreams:
            if isinstance(item, dict):
                day = item.get("day", "")
                text = item.get("text", "")
                lines.append(f"- {day}:{text}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("- (没有梦语)")

    lines += ["", "## 年轮"]
    if milestones:
        for item in milestones:
            if isinstance(item, dict):
                day = item.get("day", "")
                text = item.get("text", "")
                lines.append(f"- {day}:{text}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("- (无里程碑)")

    lines.append("")
    md = "\n".join(lines)
    return data, md
