"""CLI(bench_BLUEPRINT §13)——W4 全量:``synth``/``run``/``report``/``regress``。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import load_scenario, run_bench, synthesize
from .harness.trace import RunTrace
from .metrics import EvalContext, default_registry
from .regression.baseline import baseline_path, load_baseline, save_baseline
from .regression.gate import decide
from .reports.report import build as build_report
from .scenarios.dsl import dump_file


def _overall_str(overall) -> str:
    if isinstance(overall, str):
        return overall
    if overall is None:
        return "n/a"
    return f"{overall:.4f}"


def _cmd_synth(args: argparse.Namespace) -> int:
    scenario = synthesize(args.archetype, args.days, args.seed)
    dump_file(scenario, Path(args.out))
    print(f"BENCH synth scenario_id={scenario.scenario_id} out={args.out}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    scenario = load_scenario(Path(args.scenario))
    report = asyncio.run(
        run_bench(
            scenario,
            engine=args.engine,
            data_dir=Path(args.data_dir) if args.data_dir else None,
            out_dir=Path(args.out) if args.out else None,
        )
    )
    print(
        f"BENCH overall={_overall_str(report.overall)} vetoes={len(report.vetoes)} "
        f"scenario={report.scenario_id} rev={report.git_rev}"
    )
    if isinstance(report.overall, str) and report.overall == "FAIL":
        return 3
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    """离线重判(§5.3"同 trace 可离线重判"):只读一份既有 trace.jsonl。"""
    trace = RunTrace.load(Path(args.trace))
    registry = default_registry()
    data_dir = Path(args.data_dir) if args.data_dir else None
    scores = registry.evaluate(EvalContext(trace=trace, data_dir=data_dir))
    report = build_report(trace, scores)
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"BENCH report written -> {args.out}")
    else:
        print(payload)
    if isinstance(report.overall, str) and report.overall == "FAIL":
        return 3
    return 0


def _cmd_regress(args: argparse.Namespace) -> int:
    scenario = load_scenario(Path(args.scenario))
    report = asyncio.run(run_bench(scenario, engine=args.engine))
    root = Path(args.baseline_root) if args.baseline_root else None
    path = baseline_path(report.scenario_id, root)

    if args.rebless:
        if not args.blessed_by or not args.reason:
            print(
                "BENCH regress --rebless 需要 --blessed-by 与 --reason"
                "(§7.2 防无声漂移,理由行不得省略)",
                file=sys.stderr,
            )
            return 2
        save_baseline(
            path,
            report,
            blessed_by=args.blessed_by,
            reason=args.reason,
        )
        print(f"BENCH regress --rebless 基线已重铸 -> {path}")
        return 0

    baseline = load_baseline(path)
    verdict = decide(report, baseline)
    status = "PASS" if verdict.passed else "FAIL"
    print(f"BENCH regress {status} scenario={report.scenario_id} baseline={path}")
    if verdict.note:
        print(f"BENCH regress note: {verdict.note}")
    for failure in verdict.failures:
        print(f"BENCH regress failure: {failure}")
    return 0 if verdict.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m yelos.bench")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_synth = sub.add_parser("synth")
    p_synth.add_argument("--archetype", required=True)
    p_synth.add_argument("--days", type=int, required=True)
    p_synth.add_argument("--seed", required=True)
    p_synth.add_argument("--out", required=True)
    p_synth.set_defaults(func=_cmd_synth)

    p_run = sub.add_parser("run")
    p_run.add_argument("scenario")
    p_run.add_argument("--engine", default="fake", choices=["fake", "real"])
    p_run.add_argument("--data-dir", dest="data_dir", default=None)
    p_run.add_argument("--out", default=None)
    p_run.set_defaults(func=_cmd_run)

    p_report = sub.add_parser("report")
    p_report.add_argument("trace")
    p_report.add_argument("--data-dir", dest="data_dir", default=None)
    p_report.add_argument("--out", default=None)
    p_report.set_defaults(func=_cmd_report)

    p_regress = sub.add_parser("regress")
    p_regress.add_argument("scenario")
    p_regress.add_argument("--engine", default="fake", choices=["fake", "real"])
    p_regress.add_argument("--baseline-root", dest="baseline_root", default=None)
    p_regress.add_argument("--rebless", action="store_true")
    p_regress.add_argument("--blessed-by", dest="blessed_by", default=None)
    p_regress.add_argument("--reason", dest="reason", default=None)
    p_regress.set_defaults(func=_cmd_regress)

    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    sys.exit(main())
