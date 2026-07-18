"""Optional Weights & Biases logging."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Mapping

from ..config import ExperimentConfig


class WandbLogger:
    def __init__(self, config: ExperimentConfig, output_dir: Path) -> None:
        try:
            import wandb
        except ImportError as exc:
            raise RuntimeError(
                "Weights & Biases is not installed. Run `pip install wandb` first."
            ) from exc

        self._wandb = wandb
        config_dict = asdict(config)
        config_dict["data_root"] = str(config.data_root)
        config_dict["output_dir"] = str(config.output_dir)
        init_kwargs = {
            "project": config.wandb_project,
            "entity": config.wandb_entity,
            "name": config.wandb_run_name,
            "config": config_dict,
            "dir": str(output_dir),
        }
        try:
            self._run = wandb.init(**init_kwargs)
        except Exception:
            self._run = wandb.init(
                **init_kwargs,
                settings=wandb.Settings(start_method="thread"),
            )

    def log_epoch(self, metrics: Mapping[str, object]) -> None:
        self._wandb.log(dict(metrics), step=int(metrics["epoch"]))

    def log_summary(self, metrics: Mapping[str, object]) -> None:
        for key, value in metrics.items():
            self._run.summary[key] = value

    def log_class_accuracy(self, class_metrics: Mapping[str, float]) -> None:
        self._wandb.log(
            {
                f"class_acc/{class_name}": accuracy
                for class_name, accuracy in class_metrics.items()
            }
        )

    def finish(self) -> None:
        self._wandb.finish()
