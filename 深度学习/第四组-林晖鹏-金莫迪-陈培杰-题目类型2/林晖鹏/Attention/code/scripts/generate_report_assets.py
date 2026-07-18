#!/usr/bin/env python3
"""Generate report figures and tables from training outputs."""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / os.environ.get("LAB3_OUTPUT_DIR", "outputs")
FIG_ROOT = PROJECT_ROOT / "实验模板" / "fig" / "generated"
TABLE_ROOT = PROJECT_ROOT / "实验模板" / "tables"
MANIFEST_PATH = PROJECT_ROOT / "实验模板" / "generated_assets_manifest.txt"

os.environ["MPLCONFIGDIR"] = str(PROJECT_ROOT / ".matplotlib")

import matplotlib.pyplot as plt


def percent(value: float) -> float:
    return value * 100.0


def read_summary_metrics(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {row["metric"]: row["value"] for row in reader}


def read_epoch_metrics(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def collect_best_runs() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    family_specs = [
        ("seq2seq_rnn", ["seq2seq_rnn"]),
        ("seq2seq_attn", ["seq2seq_attn"]),
        ("seq2seq_luong", ["seq2seq_luong", "seq2seq_luong_dot", "seq2seq_luong_general", "seq2seq_luong_concat"]),
    ]
    for model_label, family_names in family_specs:
        best_row: dict[str, object] | None = None
        for family_name in family_names:
            model_dir = OUTPUT_ROOT / family_name
            if not model_dir.exists():
                continue
            run_dirs = sorted(path for path in model_dir.iterdir() if path.is_dir())
            final_non_ss = [path for path in run_dirs if path.name.startswith("final_") and "_ss_" not in path.name]
            candidate_run_dirs = final_non_ss if final_non_ss else run_dirs
            for run_dir in candidate_run_dirs:
                summary_path = run_dir / "summary_metrics.csv"
                metadata_path = run_dir / "run_metadata.json"
                if not summary_path.exists() or not metadata_path.exists():
                    continue
                summary = read_summary_metrics(summary_path)
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                row = {
                    "model": model_label,
                    "model_variant": family_name,
                    "run_name": run_dir.name,
                    "lr": metadata["lr"],
                    "hidden_size": metadata["hidden_size"],
                    "scheduled_sampling": bool(metadata.get("scheduled_sampling", False)),
                    "scheduled_sampling_strategy": metadata.get("scheduled_sampling_strategy", "fixed"),
                    "best_val_acc": float(summary["best_val_acc"]),
                    "best_val_exact_match": float(summary["best_val_exact_match"]),
                    "test_acc": float(summary["test_acc"]),
                    "test_exact_match": float(summary["test_exact_match"]),
                    "test_bleu": float(summary.get("test_bleu", 0.0)),
                    "best_val_loss": float(summary["best_val_loss"]),
                    "summary_path": str(summary_path),
                    "epoch_metrics_path": str(run_dir / "epoch_metrics.csv"),
                    "curves_path": str(run_dir / "training_curves.png"),
                    "length_bucket_path": str(run_dir / "length_bucket_metrics.csv"),
                    "all_test_path": str(run_dir / "all_test_translations.csv"),
                }
                if best_row is None or row["best_val_acc"] > best_row["best_val_acc"]:
                    best_row = row
        if best_row is not None:
            rows.append(best_row)
    return rows


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_tex_table(rows: list[dict[str, object]], path: Path) -> None:
    lines = [
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r"Model & LR & Hidden & SS & Best Val Acc & Test Exact & Test BLEU \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            f"{row['model']} & {row['lr']} & {row['hidden_size']} & "
            f"{'Y' if row['scheduled_sampling'] else 'N'} & {row['best_val_acc']:.4f} & "
            f"{row['test_exact_match']:.4f} & {row['test_bleu']:.4f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_best_run_curve_figure(rows: list[dict[str, object]]) -> plt.Figure:
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5))
    metric_specs = [
        ("train_loss", "Train Loss", "Loss"),
        ("train_acc", "Train Token Accuracy", "Accuracy"),
        ("train_exact_match", "Train Exact Match", "Exact Match"),
        ("val_loss", "Validation Loss", "Loss"),
        ("val_acc", "Validation Token Accuracy", "Accuracy"),
        ("val_exact_match", "Validation Exact Match", "Exact Match"),
    ]

    for axis, (metric_key, title, ylabel) in zip(axes.flatten(), metric_specs, strict=True):
        for row in rows:
            epoch_rows = read_epoch_metrics(Path(str(row["epoch_metrics_path"])))
            epochs = [int(item["epoch"]) for item in epoch_rows]
            metric_values = [float(item[metric_key]) for item in epoch_rows]
            if "acc" in metric_key or "exact" in metric_key:
                metric_values = [percent(value) for value in metric_values]
            axis.plot(epochs, metric_values, label=str(row["model"]))
        axis.set_title(title)
        axis.set_xlabel("Epoch")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.3)
        axis.legend()
        if ylabel in {"Accuracy", "Exact Match"}:
            axis.set_ylabel(f"{ylabel} (%)")

    fig.tight_layout()
    return fig


def save_best_run_curve_plot(rows: list[dict[str, object]], path: Path) -> None:
    if not rows:
        return
    fig = build_best_run_curve_figure(rows)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_best_run_bar_plot(rows: list[dict[str, object]], path: Path) -> None:
    if not rows:
        return
    models = [str(row["model"]) for row in rows]
    test_acc = [percent(float(row["test_acc"])) for row in rows]
    test_exact = [percent(float(row["test_exact_match"])) for row in rows]
    test_bleu = [percent(float(row["test_bleu"])) for row in rows]

    x_positions = range(len(models))
    width = 0.25

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar([x - width for x in x_positions], test_acc, width=width, label="Test Token Acc")
    ax.bar(list(x_positions), test_exact, width=width, label="Test Exact Match")
    ax.bar([x + width for x in x_positions], test_bleu, width=width, label="Test BLEU (×100)")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(models)
    ax.set_ylabel("Score (%)")
    ax.set_title("Best-Run Test Metrics")
    ax.grid(axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def compute_bleu_score(predictions: list[str], references: list[str], max_n: int = 4) -> float:
    if not predictions or not references or len(predictions) != len(references):
        return 0.0

    clipped_totals = [0 for _ in range(max_n)]
    prediction_totals = [0 for _ in range(max_n)]
    prediction_length = 0
    reference_length = 0

    for prediction, reference in zip(predictions, references):
        pred_tokens = prediction.split()
        ref_tokens = reference.split()
        prediction_length += len(pred_tokens)
        reference_length += len(ref_tokens)

        for n in range(1, max_n + 1):
            pred_ngrams: dict[tuple[str, ...], int] = {}
            ref_ngrams: dict[tuple[str, ...], int] = {}
            for i in range(max(len(pred_tokens) - n + 1, 0)):
                ngram = tuple(pred_tokens[i : i + n])
                pred_ngrams[ngram] = pred_ngrams.get(ngram, 0) + 1
            for i in range(max(len(ref_tokens) - n + 1, 0)):
                ngram = tuple(ref_tokens[i : i + n])
                ref_ngrams[ngram] = ref_ngrams.get(ngram, 0) + 1

            prediction_totals[n - 1] += max(len(pred_tokens) - n + 1, 0)
            for ngram, count in pred_ngrams.items():
                clipped_totals[n - 1] += min(count, ref_ngrams.get(ngram, 0))

    precisions = [(clipped + 1.0) / (total + 1.0) for clipped, total in zip(clipped_totals, prediction_totals)]
    if prediction_length == 0:
        return 0.0
    brevity_penalty = 1.0 if prediction_length > reference_length else math.exp(1.0 - (reference_length / prediction_length))
    return brevity_penalty * math.exp(sum(math.log(precision) for precision in precisions) / max_n)


def write_length_bucket_table(rows: list[dict[str, object]], csv_path: Path, tex_path: Path) -> None:
    table_rows: list[dict[str, object]] = []
    tex_lines = [
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"Model & Bucket & Count & Exact Match & BLEU \\",
        r"\midrule",
    ]
    for row in rows:
        bucket_rows = read_csv_rows(Path(str(row["length_bucket_path"])))
        for bucket_row in bucket_rows:
            table_rows.append(
                {
                    "model": row["model"],
                    "bucket": bucket_row["bucket"],
                    "sample_count": bucket_row["sample_count"],
                    "exact_match": bucket_row["exact_match"],
                    "bleu": bucket_row["bleu"],
                }
            )
            tex_lines.append(
                f"{row['model']} & {bucket_row['bucket']} & {bucket_row['sample_count']} & "
                f"{float(bucket_row['exact_match']):.4f} & {float(bucket_row['bleu']):.4f} \\\\"
            )
    write_csv(table_rows, csv_path)
    tex_lines.extend([r"\bottomrule", r"\end{tabular}"])
    tex_path.write_text("\n".join(tex_lines) + "\n", encoding="utf-8")


def save_length_bucket_plot(rows: list[dict[str, object]], path: Path) -> None:
    if not rows:
        return
    bucket_order = ["1-3", "4-6", "7-9"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    x_positions = range(len(bucket_order))
    width = 0.22
    for model_index, row in enumerate(rows):
        bucket_rows = {item["bucket"]: item for item in read_csv_rows(Path(str(row["length_bucket_path"])))}
        exact_values = [percent(float(bucket_rows.get(bucket, {}).get("exact_match", 0.0))) for bucket in bucket_order]
        bleu_values = [percent(float(bucket_rows.get(bucket, {}).get("bleu", 0.0))) for bucket in bucket_order]
        offsets = [x + (model_index - (len(rows) - 1) / 2) * width for x in x_positions]
        axes[0].bar(offsets, exact_values, width=width, label=str(row["model"]))
        axes[1].bar(offsets, bleu_values, width=width, label=str(row["model"]))

    for axis, title, ylabel in zip(
        axes,
        ("Exact Match by Source Length", "BLEU by Source Length"),
        ("Exact Match (%)", "BLEU (×100)"),
        strict=True,
    ):
        axis.set_xticks(list(x_positions))
        axis.set_xticklabels(bucket_order)
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(axis="y", alpha=0.3)
        axis.legend()

    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def collect_lengthwise_metrics(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    metric_rows: list[dict[str, object]] = []
    for row in rows:
        test_rows = read_csv_rows(Path(str(row["all_test_path"])))
        grouped: dict[int, list[dict[str, str]]] = {}
        for item in test_rows:
            length = int(item["source_length"])
            grouped.setdefault(length, []).append(item)

        for length in sorted(grouped):
            items = grouped[length]
            exact = sum(int(item["exact_match"]) for item in items) / max(len(items), 1)
            bleu = compute_bleu_score(
                [item["prediction_text"] for item in items],
                [item["target_text"] for item in items],
            )
            metric_rows.append(
                {
                    "model": row["model"],
                    "source_length": length,
                    "sample_count": len(items),
                    "exact_match": exact,
                    "bleu": bleu,
                }
            )
    return metric_rows


def save_lengthwise_line_plot(metric_rows: list[dict[str, object]], path: Path) -> None:
    if not metric_rows:
        return
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    models = sorted({str(row["model"]) for row in metric_rows})
    for model in models:
        model_rows = [row for row in metric_rows if str(row["model"]) == model]
        lengths = [int(row["source_length"]) for row in model_rows]
        exact_values = [percent(float(row["exact_match"])) for row in model_rows]
        bleu_values = [percent(float(row["bleu"])) for row in model_rows]
        axes[0].plot(lengths, exact_values, marker="o", label=model)
        axes[1].plot(lengths, bleu_values, marker="o", label=model)

    for axis, title, ylabel in (
        (axes[0], "Exact Match by Source Length", "Exact Match (%)"),
        (axes[1], "BLEU by Source Length", "BLEU (×100)"),
    ):
        axis.set_xlabel("Source Length")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.3)
        axis.legend()
        axis.set_xticks(sorted({int(row["source_length"]) for row in metric_rows}))
        axis.set_title(title)

    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def write_qualitative_examples(rows: list[dict[str, object]], path: Path) -> None:
    picked_rows: list[dict[str, object]] = []
    for row in rows:
        test_rows = read_csv_rows(Path(str(row["all_test_path"])))
        wrong_cases = [item for item in test_rows if item.get("exact_match") == "0"]
        for item in wrong_cases[:3]:
            picked_rows.append(
                {
                    "model": row["model"],
                    "source_text": item["source_text"],
                    "target_text": item["target_text"],
                    "prediction_text": item["prediction_text"],
                    "source_length": item["source_length"],
                }
            )
    write_csv(picked_rows, path)


def save_lr_sweep_plots() -> list[str]:
    generated: list[str] = []
    for model_dir in sorted(path for path in OUTPUT_ROOT.iterdir() if path.is_dir()):
        sweep_files = sorted(model_dir.glob(f"{model_dir.name}_*_lr_sweep_summary.csv"))
        for sweep_file in sweep_files:
            with sweep_file.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            if not rows:
                continue
            lrs = [float(row["learning_rate"]) for row in rows]
            val_acc = [float(row["best_val_acc"]) for row in rows]
            val_exact = [float(row["best_val_exact_match"]) for row in rows]

            fig, ax = plt.subplots(figsize=(6.5, 4.5))
            ax.plot(lrs, val_acc, marker="o", label="Best Val Token Acc")
            ax.plot(lrs, val_exact, marker="s", label="Best Val Exact Match")
            ax.set_xscale("log")
            ax.set_xlabel("Learning Rate")
            ax.set_ylabel("Score")
            ax.set_title(f"LR Sweep - {model_dir.name}")
            ax.grid(alpha=0.3)
            ax.legend()
            out_path = FIG_ROOT / f"{sweep_file.stem}.png"
            fig.tight_layout()
            fig.savefig(out_path, dpi=200, bbox_inches="tight")
            plt.close(fig)
            generated.append(str(out_path.relative_to(PROJECT_ROOT)))
    return generated


def main() -> None:
    FIG_ROOT.mkdir(parents=True, exist_ok=True)
    TABLE_ROOT.mkdir(parents=True, exist_ok=True)

    best_runs = collect_best_runs()
    comparison_csv = TABLE_ROOT / "model_comparison.csv"
    comparison_tex = TABLE_ROOT / "model_comparison.tex"
    length_bucket_csv = TABLE_ROOT / "length_bucket_comparison.csv"
    length_bucket_tex = TABLE_ROOT / "length_bucket_comparison.tex"
    qualitative_csv = TABLE_ROOT / "qualitative_examples.csv"
    curves_path = FIG_ROOT / "best_run_val_curves.png"
    metrics_bar_path = FIG_ROOT / "best_run_test_metrics.png"
    length_bucket_path = FIG_ROOT / "length_bucket_comparison.png"
    lengthwise_csv = TABLE_ROOT / "lengthwise_metrics.csv"
    lengthwise_plot_path = FIG_ROOT / "lengthwise_line_plot.png"

    generated_items: list[str] = []
    if best_runs:
        write_csv(best_runs, comparison_csv)
        write_tex_table(best_runs, comparison_tex)
        write_length_bucket_table(best_runs, length_bucket_csv, length_bucket_tex)
        lengthwise_rows = collect_lengthwise_metrics(best_runs)
        write_csv(lengthwise_rows, lengthwise_csv)
        write_qualitative_examples(best_runs, qualitative_csv)
        save_best_run_curve_plot(best_runs, curves_path)
        save_best_run_bar_plot(best_runs, metrics_bar_path)
        save_length_bucket_plot(best_runs, length_bucket_path)
        save_lengthwise_line_plot(lengthwise_rows, lengthwise_plot_path)
        generated_items.extend(
            [
                str(comparison_csv.relative_to(PROJECT_ROOT)),
                str(comparison_tex.relative_to(PROJECT_ROOT)),
                str(length_bucket_csv.relative_to(PROJECT_ROOT)),
                str(length_bucket_tex.relative_to(PROJECT_ROOT)),
                str(lengthwise_csv.relative_to(PROJECT_ROOT)),
                str(qualitative_csv.relative_to(PROJECT_ROOT)),
                str(curves_path.relative_to(PROJECT_ROOT)),
                str(metrics_bar_path.relative_to(PROJECT_ROOT)),
                str(length_bucket_path.relative_to(PROJECT_ROOT)),
                str(lengthwise_plot_path.relative_to(PROJECT_ROOT)),
            ]
        )

    generated_items.extend(save_lr_sweep_plots())
    MANIFEST_PATH.write_text("\n".join(generated_items) + ("\n" if generated_items else ""), encoding="utf-8")

    print(f"Generated {len(generated_items)} report assets.")
    print(f"Manifest saved to: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
