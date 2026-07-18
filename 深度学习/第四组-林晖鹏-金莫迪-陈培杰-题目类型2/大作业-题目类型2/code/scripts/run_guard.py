#!/usr/bin/env python3
"""CLI wrapper around the run-skip guard."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.run_guard import parse_expectations, should_skip_run


def build_parser():
    parser = argparse.ArgumentParser(description="Decide whether an experiment run can be skipped.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--checkpoint-name", default="best.pt")
    parser.add_argument("--expect", action="append", default=[], help="Expected config entries in key=value form.")
    return parser


def main():
    args = build_parser().parse_args()
    expectations = parse_expectations(args.expect)
    skip, reason = should_skip_run(args.output_dir, expectations, checkpoint_name=args.checkpoint_name)
    print("skip" if skip else "run")
    print(reason, file=sys.stderr)


if __name__ == "__main__":
    main()
