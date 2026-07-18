"""输出路径与 run_name 规则。"""

from __future__ import annotations

from ..config import TrainConfig


def format_float_tag(value: float) -> str:
    return f"{value:.8g}".replace("-", "m").replace(".", "p")


def build_run_name(config: TrainConfig) -> str:
    if config.run_name:
        return config.run_name
    return (
        f"{config.model}_opt{config.optimizer}_"
        f"img{config.image_size}_z{config.latent_dim}_"
        f"lr{format_float_tag(config.lr)}_bs{config.batch_size}"
    )
