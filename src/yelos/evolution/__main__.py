"""__main__.py 在整个架构中的位置:``python -m yelos.evolution`` CLI(蓝图 §2)。

子命令:``run|rollback|status|lineage``。rollback 是部署者运维动作
(蓝图 §5.3 集成点:不进 MCP 工具面,server 工具面白名单不含任何 evolution
工具——观察舱三宪法同理)。

CLI 不依赖 ``config.py`` 已接线新键(本波禁改 config.py);``--data-dir``/
``--velocity-bound`` 等 flag 直接装配一个够用的 config 代理对象,同
``build_evolution`` 的 dict/对象双形态兼容读取纪律。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import Evolution, build_evolution
from .lineage.records import LineageRecord
from .viz import (
    export_drift_json,
    export_lineage_json,
    render_drift_trajectory,
    render_fitness_history,
    render_lineage_tree,
)


def _build(args: argparse.Namespace) -> Evolution | None:
    cfg = {
        "evolution_enabled": True,
        "evolution_velocity_bound": args.velocity_bound,
        "evolution_min_days": args.min_days,
        "evolution_online_weight": args.online_weight,
        "evolution_strategy": args.strategy,
        "intrinsic_daily_cap": 3,
        "arbiter_min_gap_seconds": 180,
        "quiet_hours": "01:00-08:00",
        "lifespan_active_days": 545,
        "farewell_token_ttl_seconds": 600,
        "default_mode": "steward",
        "finitude_model": "linear",
    }
    return build_evolution(cfg, data_dir=args.data_dir)


def cmd_run(args: argparse.Namespace) -> int:
    evo = _build(args)
    if evo is None:
        print(
            "evolution 未开 opt-in(此 CLI 已强制传 evolution_enabled=True,"
            "若仍为 None 说明装配异常)",
            file=sys.stderr,
        )
        return 1
    problems = evo.validate()
    if problems:
        for p in problems:
            print(f"registry problem: {p}", file=sys.stderr)
        return 2
    summary = evo.run(args.generations, now_fn=time.time)
    for outcome in summary.outcomes:
        print(f"gen={outcome.gen} verdict={outcome.verdict} reasons={outcome.reasons}")
    print(f"final_gen={summary.final_gen}")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    evo = _build(args)
    if evo is None:
        return 1
    try:
        path = evo.rollback(args.gen, now_fn=time.time)
    except Exception as exc:  # noqa: BLE001 CLI 边界,诚实报错不崩栈
        print(f"rollback failed: {exc}", file=sys.stderr)
        return 3
    print(f"overlay 已更新: {path}(重启后生效)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    evo = _build(args)
    if evo is None:
        return 1
    genome = evo.current_genome()
    provenance = evo.ledger.current_provenance()
    print(
        json.dumps(
            {"genome": genome, "provenance": provenance}, ensure_ascii=False, indent=2
        )
    )
    return 0


def cmd_lineage(args: argparse.Namespace) -> int:
    evo = _build(args)
    if evo is None:
        return 1
    records: list[LineageRecord] = evo.ledger.all_records()
    if args.svg:
        out_dir = Path(args.svg)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "lineage_tree.svg").write_text(
            render_lineage_tree(records), encoding="utf-8"
        )
        (out_dir / "drift_trajectory.svg").write_text(
            render_drift_trajectory(records), encoding="utf-8"
        )
        (out_dir / "fitness_history.svg").write_text(
            render_fitness_history(records), encoding="utf-8"
        )
        print(f"SVG 已写入: {out_dir}")
        return 0
    print(
        json.dumps(
            {
                "lineage": export_lineage_json(records),
                "drift": export_drift_json(records),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m yelos.evolution")
    parser.add_argument("--data-dir", default="~/.yelos")
    parser.add_argument("--velocity-bound", type=float, default=0.05)
    parser.add_argument("--min-days", type=int, default=7)
    parser.add_argument("--online-weight", type=float, default=0.0)
    parser.add_argument("--strategy", default="pattern_search")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("generations", type=int, nargs="?", default=1)
    p_run.set_defaults(func=cmd_run)

    p_rb = sub.add_parser("rollback")
    p_rb.add_argument("--gen", type=int, required=True)
    p_rb.set_defaults(func=cmd_rollback)

    p_st = sub.add_parser("status")
    p_st.set_defaults(func=cmd_status)

    p_ln = sub.add_parser("lineage")
    p_ln.add_argument("--svg", default=None, help="导出 SVG 到该目录")
    p_ln.set_defaults(func=cmd_lineage)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
