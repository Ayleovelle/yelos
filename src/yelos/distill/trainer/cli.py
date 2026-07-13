"""在整个架构中的位置:唯一训练门(蓝图 §1/§7)。

``python -m yelos.distill.trainer <corpus.jsonl> <out_dir> --tier ngram``。
训练是部署者动作,不是她的动作——不进 MCP 工具面、不进心跳(§7 接线点4)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import TrainConfig, get_trainer
from .protocol import DistillExtrasMissing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m yelos.distill.trainer")
    parser.add_argument("corpus", type=Path, help="corpus.jsonl 路径")
    parser.add_argument("out_dir", type=Path, help="模型输出目录")
    parser.add_argument(
        "--tier", default="ngram", choices=("ngram", "rnn", "transformer")
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-minutes", type=int, default=30)
    parser.add_argument(
        "--tier-params",
        type=str,
        default="{}",
        help="JSON 字符串,逐档专属超参(order/hidden/epochs 等)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        tier_params = json.loads(args.tier_params)
    except (ValueError, TypeError):
        print("--tier-params 不是合法 JSON", file=sys.stderr)
        return 2
    cfg = TrainConfig(
        seed=args.seed, max_minutes=args.max_minutes, tier_params=tier_params
    )
    try:
        trainer = get_trainer(args.tier)
        report = trainer.train(args.corpus, args.out_dir, cfg)
    except DistillExtrasMissing as exc:
        print(f"extras 缺失:{exc}", file=sys.stderr)
        return 3
    except ValueError as exc:
        print(f"训练拒绝:{exc}", file=sys.stderr)
        return 4
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
