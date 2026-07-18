#!/usr/bin/env python3
"""Lab4 报告素材生成脚本。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import build_model
from src.utils.io import ensure_dir
from src.utils.runtime import set_seed, setup_matplotlib

setup_matplotlib(PROJECT_ROOT)

import matplotlib.pyplot as plt
import torch
import torchvision.utils as vutils

FIG_ROOT = PROJECT_ROOT / "实验模板" / "fig" / "generated"
TABLE_ROOT = PROJECT_ROOT / "实验模板" / "tables"
MANIFEST_PATH = PROJECT_ROOT / "实验模板" / "generated_assets_manifest.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate report assets for lab4")
    parser.add_argument("--gan-run", type=str, default=None, help="Run name under outputs/gan/")
    parser.add_argument("--gan-deep-run", type=str, default=None, help="Run name under outputs/gan_deep/")
    parser.add_argument("--dcgan-run", type=str, default=None, help="Run name under outputs/dcgan/")
    parser.add_argument("--output-root", type=str, default=str(PROJECT_ROOT / "outputs"), help="Training output root.")
    parser.add_argument("--fixed-sample-count", type=int, default=8, help="Number of fixed noise samples.")
    parser.add_argument("--latent-analysis-count", type=int, default=100, help="Latent vector dimension / analysis pool size.")
    parser.add_argument("--latent-analysis-picks", type=int, default=5, help="How many latent coordinates to perturb.")
    parser.add_argument("--latent-perturbations", type=int, default=3, help="How many perturbation levels per coordinate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    return parser.parse_args()


def load_run_bundle(output_root: Path, model: str, run_name: str) -> tuple[dict[str, object], dict[str, object], Path]:
    run_dir = output_root / model / run_name
    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    checkpoint = torch.load(run_dir / "best_model.pth", map_location="cpu")
    return metadata, checkpoint, run_dir


def build_generator_from_metadata(metadata: dict[str, object], checkpoint: dict[str, object]):
    generator, _ = build_model(
        str(metadata["model"]),
        latent_dim=int(metadata["latent_dim"]),
        hidden_dim=int(metadata.get("hidden_dim", 128)),
        image_size=int(metadata["image_size"]),
        image_channels=int(metadata["image_channels"]),
        generator_base_channels=int(metadata.get("generator_base_channels", 64)),
        discriminator_base_channels=int(metadata.get("discriminator_base_channels", 64)),
    )
    generator.load_state_dict(checkpoint["generator_state_dict"])
    generator.eval()
    return generator


def build_noise(model: str, sample_count: int, latent_dim: int, seed: int) -> torch.Tensor:
    generator = torch.Generator().manual_seed(seed)
    if model == "dcgan":
        return torch.randn(sample_count, latent_dim, 1, 1, generator=generator)
    return torch.randn(sample_count, latent_dim, generator=generator)


def save_grid(images: torch.Tensor, path: Path, nrow: int) -> None:
    grid = vutils.make_grid(images.detach().cpu(), nrow=nrow, normalize=True, pad_value=0.3)
    fig = plt.figure(figsize=(max(8, nrow), max(8, images.size(0) / max(nrow, 1))))
    plt.axis("off")
    plt.imshow(grid.permute(1, 2, 0).numpy(), cmap="gray" if images.size(1) == 1 else None)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def select_active_dims(generator, model: str, latent_dim: int, pick_count: int,
                        n_probe: int = 32, delta: float = 2.5) -> list[int]:
    """选取“最活跃”的隐维度：对每个维度施加固定扰动，测量生成图的平均变化幅度，
    取变化最大的 pick_count 个维度。避免随机选到对输出几乎无影响的不活跃维度。"""
    set_seed(0)
    base = torch.randn(n_probe, latent_dim)
    with torch.no_grad():
        base_img = generator(adapt_noise_for_model(model, base))
        scores = torch.zeros(latent_dim)
        for d in range(latent_dim):
            pert = base.clone()
            pert[:, d] += delta
            img = generator(adapt_noise_for_model(model, pert))
            scores[d] = (img - base_img).abs().mean()
    return sorted(torch.topk(scores, pick_count).indices.tolist())


def build_latent_variations(
    generator,
    model: str,
    latent_dim: int,
    sample_count: int,
    pick_count: int,
    perturbations: int,
    seed: int,
) -> list[dict[str, object]]:
    set_seed(seed)
    base = torch.randn(sample_count, latent_dim)
    picks = select_active_dims(generator, model, latent_dim, pick_count)
    deltas = torch.linspace(-2.5, 2.5, perturbations)

    rows: list[dict[str, object]] = []
    for dimension in picks:
        for delta in deltas.tolist():
            variant = base.clone()
            variant[:, dimension] += float(delta)
            rows.append({"dimension": dimension, "delta": float(delta), "images": variant})
    return rows


def adapt_noise_for_model(model: str, noise: torch.Tensor) -> torch.Tensor:
    if model == "dcgan":
        return noise.unsqueeze(-1).unsqueeze(-1)
    return noise


def save_latent_analysis_figure(generator, model: str, latent_rows: list[dict[str, object]], path: Path) -> None:
    image_rows = []
    for row in latent_rows:
        noise = adapt_noise_for_model(model, row["images"])
        with torch.no_grad():
            image_rows.append(generator(noise))
    stacked = torch.cat(image_rows, dim=0)
    save_grid(stacked, path, nrow=latent_rows[0]["images"].shape[0])


def main() -> None:
    args = parse_args()
    ensure_dir(FIG_ROOT)
    ensure_dir(TABLE_ROOT)
    manifest_lines: list[str] = []
    output_root = Path(args.output_root)

    model_runs = [
        ("gan", args.gan_run),
        ("gan_deep", args.gan_deep_run),
        ("dcgan", args.dcgan_run),
    ]
    model_runs = [(model, run) for model, run in model_runs if run]
    if not model_runs:
        raise SystemExit("No run specified; pass at least one of --gan-run/--gan-deep-run/--dcgan-run.")

    for model, run_name in model_runs:
        metadata, checkpoint, run_dir = load_run_bundle(output_root, model, run_name)
        generator = build_generator_from_metadata(metadata, checkpoint)
        latent_dim = int(metadata["latent_dim"])

        fixed_noise = build_noise(model, args.fixed_sample_count, latent_dim, args.seed)
        with torch.no_grad():
            fixed_images = generator(fixed_noise)
        fixed_path = FIG_ROOT / f"{model}_{run_name}_fixed_samples.png"
        save_grid(fixed_images, fixed_path, nrow=args.fixed_sample_count)
        manifest_lines.append(str(fixed_path))

        latent_rows = build_latent_variations(
            generator=generator,
            model=model,
            latent_dim=args.latent_analysis_count,
            sample_count=args.fixed_sample_count,
            pick_count=args.latent_analysis_picks,
            perturbations=args.latent_perturbations,
            seed=args.seed,
        )
        latent_path = FIG_ROOT / f"{model}_{run_name}_latent_variations.png"
        save_latent_analysis_figure(generator, model, latent_rows, latent_path)
        manifest_lines.append(str(latent_path))

        summary_csv = run_dir / "summary_metrics.csv"
        target_summary = TABLE_ROOT / f"{model}_{run_name}_summary_metrics.csv"
        target_summary.write_text(summary_csv.read_text(encoding="utf-8"), encoding="utf-8")
        manifest_lines.append(str(target_summary))

    MANIFEST_PATH.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    print(f"Saved manifest to: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
