#!/usr/bin/env python3
"""Judge generation quality with a trained name classifier."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

import matplotlib.pyplot as plt
import numpy as np
import torch

from src.constants import NUM_CHARACTERS
from src.data import line_to_tensor, unicode_to_ascii
from src.models import build_model
from src.utils.io import ensure_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate generation category fidelity with a trained classifier.")
    parser.add_argument(
        "--classifier-run",
        required=True,
        help="Path to a finished classification run directory containing run_metadata.json and best_model.pth.",
    )
    parser.add_argument(
        "--generation-runs",
        nargs="+",
        required=True,
        help="One or more generation run directories containing generated_samples.txt.",
    )
    parser.add_argument(
        "--report-name",
        default="fidelity_report",
        help="Output report directory name under outputs/generation/fidelity_reports/.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "outputs" / "generation" / "fidelity_reports"),
        help="Directory for evaluation outputs.",
    )
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Inference device for the classifier.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_classifier(run_dir: Path, device: torch.device):
    metadata = load_json(run_dir / "run_metadata.json")
    class_names = [str(name) for name in metadata["class_names"]]
    model = build_model(
        model_name=str(metadata["model"]),
        input_size=NUM_CHARACTERS,
        hidden_size=int(metadata["hidden_size"]),
        output_size=int(metadata["class_count"]),
        num_layers=int(metadata.get("num_layers", 1)),
        dropout=float(metadata.get("dropout", 0.0)),
    ).to(device)
    state_dict = torch.load(run_dir / "best_model.pth", map_location=device)
    model.load_state_dict(state_dict)
    model.eval()
    return model, class_names, metadata


def parse_generated_samples(path: Path) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    current_category: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current_category = line[1:-1]
            grouped.setdefault(current_category, [])
            continue
        if current_category is None:
            continue
        grouped[current_category].append(unicode_to_ascii(line))
    return grouped


def predict_name(model, name: str, device: torch.device) -> torch.Tensor:
    sequence = line_to_tensor(name).unsqueeze(1).to(device)
    lengths = torch.tensor([sequence.size(0)], dtype=torch.long, device=device)
    with torch.no_grad():
        log_probs = model(sequence, lengths)
    return log_probs[0].cpu()


def save_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_summary(detail_rows: list[dict[str, object]], class_names: list[str]) -> list[dict[str, object]]:
    summary_rows: list[dict[str, object]] = []
    run_names = sorted({str(row["generation_run"]) for row in detail_rows})
    for run_name in run_names:
        run_rows = [row for row in detail_rows if row["generation_run"] == run_name]
        for category_name in class_names:
            rows = [row for row in run_rows if row["conditioned_category"] == category_name]
            if not rows:
                continue
            count = len(rows)
            matches = sum(int(row["is_match"]) for row in rows)
            summary_rows.append(
                {
                    "generation_run": run_name,
                    "conditioned_category": category_name,
                    "generated_count": count,
                    "category_fidelity": matches / count,
                    "avg_target_confidence": sum(float(row["target_category_confidence"]) for row in rows) / count,
                    "avg_predicted_confidence": sum(float(row["predicted_confidence"]) for row in rows) / count,
                    "avg_name_length": sum(int(row["name_length"]) for row in rows) / count,
                }
            )

        count = len(run_rows)
        matches = sum(int(row["is_match"]) for row in run_rows)
        summary_rows.append(
            {
                "generation_run": run_name,
                "conditioned_category": "ALL",
                "generated_count": count,
                "category_fidelity": matches / max(count, 1),
                "avg_target_confidence": sum(float(row["target_category_confidence"]) for row in run_rows) / max(count, 1),
                "avg_predicted_confidence": sum(float(row["predicted_confidence"]) for row in run_rows) / max(count, 1),
                "avg_name_length": sum(int(row["name_length"]) for row in run_rows) / max(count, 1),
            }
        )
    return summary_rows


def save_overall_fidelity_bar(summary_rows: list[dict[str, object]], path: Path) -> None:
    overall_rows = [row for row in summary_rows if row["conditioned_category"] == "ALL"]
    if not overall_rows:
        return
    labels = [str(row["generation_run"]) for row in overall_rows]
    values = [float(row["category_fidelity"]) for row in overall_rows]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(labels, values, color=["#4C78A8", "#F58518", "#54A24B", "#B279A2"][: len(labels)])
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Fidelity")
    ax.set_title("Overall Category Fidelity")
    ax.grid(axis="y", alpha=0.3)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_category_fidelity_bar(summary_rows: list[dict[str, object]], class_names: list[str], path: Path) -> None:
    plot_rows = [row for row in summary_rows if row["conditioned_category"] != "ALL"]
    run_names = sorted({str(row["generation_run"]) for row in plot_rows})
    if not run_names:
        return

    x = np.arange(len(class_names))
    width = 0.8 / max(len(run_names), 1)
    fig, ax = plt.subplots(figsize=(14, 5.5))

    for index, run_name in enumerate(run_names):
        fidelity_map = {
            str(row["conditioned_category"]): float(row["category_fidelity"])
            for row in plot_rows
            if row["generation_run"] == run_name
        }
        values = [fidelity_map.get(class_name, 0.0) for class_name in class_names]
        ax.bar(x + (index - (len(run_names) - 1) / 2) * width, values, width=width, label=run_name)

    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Fidelity")
    ax.set_title("Per-category Fidelity by Generation Model")
    ax.set_xticks(x)
    ax.set_xticklabels(class_names, rotation=60, ha="right")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=min(3, len(run_names)))
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_confusion_outputs(
    detail_rows: list[dict[str, object]],
    class_names: list[str],
    output_dir: Path,
) -> None:
    class_to_index = {name: index for index, name in enumerate(class_names)}
    run_names = sorted({str(row["generation_run"]) for row in detail_rows})
    for run_name in run_names:
        matrix = np.zeros((len(class_names), len(class_names)), dtype=np.int64)
        for row in detail_rows:
            if row["generation_run"] != run_name:
                continue
            true_index = class_to_index[str(row["conditioned_category"])]
            pred_index = class_to_index[str(row["predicted_category"])]
            matrix[true_index, pred_index] += 1

        csv_path = output_dir / f"{run_name}_fidelity_confusion_matrix.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["conditioned/predicted"] + class_names)
            for class_name, row_values in zip(class_names, matrix.tolist()):
                writer.writerow([class_name] + row_values)

        row_sums = np.clip(matrix.sum(axis=1, keepdims=True), a_min=1, a_max=None)
        normalized = matrix / row_sums
        fig, ax = plt.subplots(figsize=(8, 7))
        image = ax.imshow(normalized, cmap="Blues")
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        ax.set_xticks(np.arange(len(class_names)))
        ax.set_yticks(np.arange(len(class_names)))
        ax.set_xticklabels(class_names, rotation=90)
        ax.set_yticklabels(class_names)
        ax.set_xlabel("Classifier Predicted Category")
        ax.set_ylabel("Generator Conditioned Category")
        ax.set_title(f"Category Fidelity Confusion: {run_name}")
        fig.tight_layout()
        fig.savefig(output_dir / f"{run_name}_fidelity_confusion_matrix.png", dpi=200, bbox_inches="tight")
        plt.close(fig)


def main() -> None:
    args = parse_args()
    classifier_run = Path(args.classifier_run).resolve()
    generation_runs = [Path(path).resolve() for path in args.generation_runs]
    output_dir = Path(args.output_dir).resolve() / args.report_name
    ensure_dir(output_dir)

    device = torch.device(args.device)
    model, class_names, classifier_metadata = load_classifier(classifier_run, device)
    class_to_index = {name: index for index, name in enumerate(class_names)}

    detail_rows: list[dict[str, object]] = []
    for generation_run in generation_runs:
        generated = parse_generated_samples(generation_run / "generated_samples.txt")
        for conditioned_category, names in generated.items():
            if conditioned_category not in class_to_index:
                continue
            target_index = class_to_index[conditioned_category]
            for name in names:
                log_probs = predict_name(model, name, device)
                probs = log_probs.exp()
                predicted_index = int(torch.argmax(probs).item())
                detail_rows.append(
                    {
                        "generation_run": generation_run.name,
                        "conditioned_category": conditioned_category,
                        "generated_name": name,
                        "predicted_category": class_names[predicted_index],
                        "predicted_confidence": float(probs[predicted_index].item()),
                        "target_category_confidence": float(probs[target_index].item()),
                        "is_match": int(predicted_index == target_index),
                        "name_length": len(name),
                    }
                )

    if not detail_rows:
        raise RuntimeError("No generated samples were evaluated. Check generated_samples.txt paths and category names.")

    summary_rows = build_summary(detail_rows, class_names)
    save_csv(output_dir / "fidelity_per_name.csv", detail_rows)
    save_csv(output_dir / "fidelity_summary.csv", summary_rows)
    save_overall_fidelity_bar(summary_rows, output_dir / "overall_fidelity.png")
    save_category_fidelity_bar(summary_rows, class_names, output_dir / "category_fidelity.png")
    save_confusion_outputs(detail_rows, class_names, output_dir)

    judge_metadata = {
        "classifier_run": str(classifier_run),
        "classifier_model": classifier_metadata["model"],
        "classifier_hidden_size": classifier_metadata["hidden_size"],
        "generation_runs": [str(path) for path in generation_runs],
        "evaluated_name_count": len(detail_rows),
        "class_names": class_names,
    }
    (output_dir / "judge_metadata.json").write_text(json.dumps(judge_metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Saved fidelity report to: {output_dir}")
    print(f"- per-name details: {output_dir / 'fidelity_per_name.csv'}")
    print(f"- summary: {output_dir / 'fidelity_summary.csv'}")
    print(f"- overall fidelity plot: {output_dir / 'overall_fidelity.png'}")
    print(f"- per-category plot: {output_dir / 'category_fidelity.png'}")


if __name__ == "__main__":
    main()
