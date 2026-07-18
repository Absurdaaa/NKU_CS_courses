"""Helpers for skipping runs when an equivalent output directory already exists."""

import json
from pathlib import Path


def _parse_literal(value):
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "none":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_expectations(items):
    expectations = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid expectation '{item}'. Use key=value.")
        key, value = item.split("=", 1)
        expectations[key] = _parse_literal(value)
    return expectations


def diff_config(config, expectations):
    mismatches = {}
    for key, expected_value in expectations.items():
        actual_value = config.get(key)
        if actual_value != expected_value:
            mismatches[key] = {"expected": expected_value, "actual": actual_value}
    return mismatches


def should_skip_run(output_dir, expectations, checkpoint_name="best.pt"):
    output_dir = Path(output_dir)
    config_path = output_dir / "config.json"
    checkpoint_path = output_dir / checkpoint_name

    if not config_path.exists() or not checkpoint_path.exists():
        return False, "missing config or checkpoint"

    config = json.loads(config_path.read_text(encoding="utf-8"))
    mismatches = diff_config(config, expectations)
    if mismatches:
        return False, json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
    return True, "matching config and checkpoint found"
