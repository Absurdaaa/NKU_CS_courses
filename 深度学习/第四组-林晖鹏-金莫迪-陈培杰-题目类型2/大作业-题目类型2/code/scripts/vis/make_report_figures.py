"""Generate report-ready figures from synced experiment summaries.

Inputs default to the CSV files fetched from the remote servers into:
  results/remote_sync/summaries/

Outputs are written to:
  docs/figures/
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUMMARY_DIR = ROOT / "results" / "remote_sync" / "summaries"
DEFAULT_OUT_DIR = ROOT / "docs" / "figures"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def find_row(rows: list[dict[str, str]], needle: str, occurrence: int = 0) -> dict[str, str]:
    matches = [row for row in rows if needle in row.get("checkpoint", "")]
    if occurrence >= len(matches):
        raise KeyError(f"Could not find occurrence {occurrence} for {needle}")
    return matches[occurrence]


def plot_bar(ax, labels: list[str], values: list[float], colors: list[str], title: str, ylabel: str) -> None:
    bars = ax.bar(range(len(labels)), values, color=colors, edgecolor="#222222", linewidth=0.8)
    ax.set_xticks(range(len(labels)), labels, rotation=18, ha="right")
    ax.set_title(title, fontsize=12)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.set_axisbelow(True)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.001, f"{value:.3f}", ha="center", va="bottom", fontsize=8)


def save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {path}")


def make_c3net_module_plot(c3_rows: list[dict[str, str]], ext_rows: list[dict[str, str]], out_dir: Path) -> None:
    labels = ["Base", "+PPM", "+Cue", "+CSCM", "CSCM-only", "UG-CSCM", "Norm-CSCM"]
    ecssd = [
        as_float(find_row(c3_rows, "a0_base"), "max_f_measure"),
        as_float(find_row(c3_rows, "b2_context"), "max_f_measure"),
        as_float(find_row(c3_rows, "b3_cue"), "max_f_measure"),
        as_float(find_row(c3_rows, "b4_full"), "max_f_measure"),
        as_float(find_row(c3_rows, "b_cscm_only"), "max_f_measure"),
        as_float(find_row(c3_rows, "b4_ug"), "max_f_measure"),
        as_float(find_row(c3_rows, "b4_norm"), "max_f_measure"),
    ]
    duts = [
        as_float(find_row(ext_rows, "a0_base"), "max_f_measure"),
        as_float(find_row(ext_rows, "b2_context"), "max_f_measure"),
        as_float(find_row(ext_rows, "b3_cue"), "max_f_measure"),
        as_float(find_row(ext_rows, "b4_full"), "max_f_measure"),
        as_float(find_row(ext_rows, "b_cscm_only"), "max_f_measure"),
        None,
        None,
    ]
    colors = ["#7b8cde", "#9ac0f4", "#8bd3c7", "#ffb86b", "#f28f8f", "#c88df0", "#bfbfbf"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    plot_bar(axes[0], labels, ecssd, colors, "C3Net Module Gains on ECSSD", "max-F")
    valid_labels = [label for label, value in zip(labels, duts) if value is not None]
    valid_values = [value for value in duts if value is not None]
    valid_colors = [color for color, value in zip(colors, duts) if value is not None]
    plot_bar(axes[1], valid_labels, valid_values, valid_colors, "C3Net Chain on DUTS-TE", "max-F")
    save(fig, out_dir / "c3net_module_effect.png")


def make_ctd_module_plot(ctd_rows: list[dict[str, str]], ext_rows: list[dict[str, str]], out_dir: Path) -> None:
    labels = ["Spatial", "+Semantic", "+Boundary", "No CAM", "Fuse", "Fuse+Boundary"]
    ecssd = [
        as_float(find_row(ctd_rows, "ctd_base"), "max_f_measure"),
        as_float(find_row(ctd_rows, "ctd_sem"), "max_f_measure"),
        as_float(find_row(ctd_rows, "ctd_full"), "max_f_measure"),
        as_float(find_row(ctd_rows, "ctd_nocam"), "max_f_measure"),
        as_float(find_row(ctd_rows, "fuse"), "max_f_measure"),
        as_float(find_row(ctd_rows, "fuse_full"), "max_f_measure"),
    ]
    duts = [
        as_float(find_row(ext_rows, "ctd_base"), "max_f_measure"),
        as_float(find_row(ext_rows, "ctd_sem"), "max_f_measure"),
        as_float(find_row(ext_rows, "ctd_full"), "max_f_measure"),
    ]
    colors = ["#7b8cde", "#57c6a9", "#ffb86b", "#f28f8f", "#7fd0ff", "#d3a6ff"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    plot_bar(axes[0], labels, ecssd, colors, "CTD Route on ECSSD", "max-F")
    plot_bar(axes[1], ["Spatial", "+Semantic", "+Boundary"], duts, colors[:3], "CTD Route on DUTS-TE", "max-F")
    save(fig, out_dir / "ctd_module_effect.png")


def make_loo_plot(loo_rows: list[dict[str, str]], c3_rows: list[dict[str, str]], ctd_rows: list[dict[str, str]], out_dir: Path) -> None:
    c3_full = as_float(find_row(c3_rows, "b4_full"), "max_f_measure")
    ctd_full = as_float(find_row(ctd_rows, "ctd_full"), "max_f_measure")
    labels = [
        "C3 - no edge",
        "C3 - no deep sup",
        "C3 - no PPM",
        "C3 - no PPM/edge",
        "CTD - no semantic",
        "CTD - no sem/CAM",
    ]
    base_values = [c3_full, c3_full, c3_full, c3_full, ctd_full, ctd_full]
    removed_values = [
        as_float(find_row(loo_rows, "c3_loo_no_edge"), "max_f_measure"),
        as_float(find_row(loo_rows, "c3_loo_no_deepsup"), "max_f_measure"),
        as_float(find_row(loo_rows, "c3_loo_no_ppm"), "max_f_measure"),
        as_float(find_row(loo_rows, "c3_no_ppm_edge"), "max_f_measure"),
        as_float(find_row(loo_rows, "ctd_loo_no_sem"), "max_f_measure"),
        as_float(find_row(loo_rows, "ctd_no_sem_cam"), "max_f_measure"),
    ]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    x = range(len(labels))
    width = 0.38
    ax.bar([i - width / 2 for i in x], base_values, width=width, color="#ffb86b", label="Full model")
    ax.bar([i + width / 2 for i in x], removed_values, width=width, color="#7b8cde", label="After removal")
    ax.set_xticks(list(x), labels, rotation=18, ha="right")
    ax.set_title("Leave-One-Out Evidence: Each Removed Module Costs Performance")
    ax.set_ylabel("max-F")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.set_axisbelow(True)
    save(fig, out_dir / "loo_ablation_effect.png")


def make_external_compare_plot(
    ext_rows_a: list[dict[str, str]],
    ext_rows_b: list[dict[str, str]],
    out_dir: Path,
) -> None:
    model_to_vals: dict[str, dict[str, float]] = defaultdict(dict)
    # server B rows are emitted as DUT-OMRON then DUTS-TE for each model.
    ordered_models = ["egnet_r18", "pfa_r18", "sinet_r18", "poolnet_r18", "dss_r18", "f3net_r18"]
    idx = 0
    for model in ordered_models:
        model_rows = ext_rows_b[idx : idx + 2]
        model_to_vals[model]["DUT-OMRON"] = as_float(model_rows[0], "max_f_measure")
        model_to_vals[model]["DUTS-TE"] = as_float(model_rows[1], "max_f_measure")
        idx += 2

    model_to_vals["baseline"]["DUTS-TE"] = as_float(find_row(ext_rows_a, "a0_base", 0), "max_f_measure")
    model_to_vals["baseline"]["DUT-OMRON"] = as_float(find_row(ext_rows_a, "a0_base", 1), "max_f_measure")
    model_to_vals["c3net"]["DUTS-TE"] = as_float(find_row(ext_rows_a, "b4_full", 0), "max_f_measure")
    model_to_vals["c3net"]["DUT-OMRON"] = as_float(find_row(ext_rows_a, "b4_full", 1), "max_f_measure")
    model_to_vals["ctd_sem"]["DUTS-TE"] = as_float(find_row(ext_rows_a, "ctd_sem", 0), "max_f_measure")
    model_to_vals["ctd_sem"]["DUT-OMRON"] = as_float(find_row(ext_rows_a, "ctd_sem", 1), "max_f_measure")

    labels = ["baseline", "ctd_sem", "c3net", "poolnet", "pfa", "egnet", "sinet", "dss", "f3net"]
    duts = [
        model_to_vals["baseline"]["DUTS-TE"],
        model_to_vals["ctd_sem"]["DUTS-TE"],
        model_to_vals["c3net"]["DUTS-TE"],
        model_to_vals["poolnet_r18"]["DUTS-TE"],
        model_to_vals["pfa_r18"]["DUTS-TE"],
        model_to_vals["egnet_r18"]["DUTS-TE"],
        model_to_vals["sinet_r18"]["DUTS-TE"],
        model_to_vals["dss_r18"]["DUTS-TE"],
        model_to_vals["f3net_r18"]["DUTS-TE"],
    ]
    dutom = [
        model_to_vals["baseline"]["DUT-OMRON"],
        model_to_vals["ctd_sem"]["DUT-OMRON"],
        model_to_vals["c3net"]["DUT-OMRON"],
        model_to_vals["poolnet_r18"]["DUT-OMRON"],
        model_to_vals["pfa_r18"]["DUT-OMRON"],
        model_to_vals["egnet_r18"]["DUT-OMRON"],
        model_to_vals["sinet_r18"]["DUT-OMRON"],
        model_to_vals["dss_r18"]["DUT-OMRON"],
        model_to_vals["f3net_r18"]["DUT-OMRON"],
    ]

    fig, ax = plt.subplots(figsize=(12, 4.8))
    x = range(len(labels))
    width = 0.38
    ax.bar([i - width / 2 for i in x], duts, width=width, color="#57c6a9", label="DUTS-TE")
    ax.bar([i + width / 2 for i in x], dutom, width=width, color="#7b8cde", label="DUT-OMRON")
    ax.set_xticks(list(x), labels, rotation=18, ha="right")
    ax.set_ylabel("max-F")
    ax.set_title("Cross-Dataset Generalization of Aligned Seed-42 Models")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.set_axisbelow(True)
    save(fig, out_dir / "external_generalization.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-dir", type=Path, default=DEFAULT_SUMMARY_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    c3_rows = read_csv(args.summary_dir / "serverA_c3net_seed42.csv")
    ctd_rows = read_csv(args.summary_dir / "serverA_ctd_seed42.csv")
    loo_rows = read_csv(args.summary_dir / "serverA_loo_seed42.csv")
    ext_rows_a = read_csv(args.summary_dir / "serverA_external_eval.csv")
    ext_rows_b = read_csv(args.summary_dir / "serverB_external_cmp.csv")

    make_c3net_module_plot(c3_rows, ext_rows_a, args.out_dir)
    make_ctd_module_plot(ctd_rows, ext_rows_a, args.out_dir)
    make_loo_plot(loo_rows, c3_rows, ctd_rows, args.out_dir)
    make_external_compare_plot(ext_rows_a, ext_rows_b, args.out_dir)


if __name__ == "__main__":
    main()
