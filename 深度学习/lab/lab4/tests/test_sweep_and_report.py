from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_report_assets import build_latent_variations
from sweep_lr import summarize_runs


def test_summarize_runs_sorts_by_best_validation_score(tmp_path: Path) -> None:
    rows = [
        {
            "run_name": "run_b",
            "model": "gan",
            "optimizer": "adam",
            "learning_rate": "0.0005",
            "best_val_generator_loss": "0.1",
            "best_val_discriminator_loss": "9.5",
            "best_validation_score": "10.2",
            "best_epoch": "5",
            "test_generator_loss": "0.9",
            "test_discriminator_loss": "1.0",
        },
        {
            "run_name": "run_a",
            "model": "gan",
            "optimizer": "adam",
            "learning_rate": "0.0002",
            "best_val_generator_loss": "0.9",
            "best_val_discriminator_loss": "1.0",
            "best_validation_score": "1.4",
            "best_epoch": "4",
            "test_generator_loss": "0.7",
            "test_discriminator_loss": "1.0",
        },
    ]
    summary_path, best_lr_path = summarize_runs(
        output_root=tmp_path,
        model="gan",
        optimizer="adam",
        rows=rows,
    )

    assert summary_path.exists()
    assert best_lr_path.exists()
    assert best_lr_path.read_text(encoding="utf-8").strip() == "0.0002"


def test_build_latent_variations_returns_15_rows() -> None:
    rows = build_latent_variations(
        latent_dim=100,
        sample_count=8,
        pick_count=5,
        perturbations=3,
        seed=42,
    )

    assert len(rows) == 15
    assert rows[0]["images"].shape[0] == 8
