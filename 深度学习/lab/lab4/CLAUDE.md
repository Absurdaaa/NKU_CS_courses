# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Lab4 is a GAN/DCGAN training framework for **FashionMNIST**. It trains a vanilla fully-connected GAN and a convolutional DCGAN, sweeps learning rates, and generates figures/tables for a lab report (`docs/要求.md` describes the assignment: loss curves, model structures, 8 fixed-noise samples, and a 5×3 latent-perturbation analysis of 15×8 images).

The same multi-file skeleton convention is shared with `../lab1`, `../lab2`, `../lab3` (see `../LAB_PROJECT_STRUCTURE.md`).

## Commands

All commands run from the `lab4/` directory.

```bash
# Run the full pipeline: sweep LRs -> train final models -> generate report assets
./run.sh

# Single training run (writes to outputs/<model>/<run_name>/)
python3 train.py --model gan   --run-name myrun --epochs 100 --batch-size 512 --lr 0.0002 --optimizer adam
python3 train.py --model dcgan --run-name myrun --epochs 100 --batch-size 512 --lr 0.0002 --optimizer adam

# Learning-rate sweep (spawns one train.py subprocess per lr; skips runs whose summary_metrics.csv already exists)
python3 sweep_lr.py --model gan --optimizer adam --epochs 100 --batch-size 512 --lrs 0.001 0.0005 0.0002 0.0001

# Report assets (reads best_model.pth from two finished runs)
python3 scripts/generate_report_assets.py --gan-run final_gan_fashionmnist --dcgan-run final_dcgan_fashionmnist

# Tests (no pytest config; each test file self-injects PROJECT_ROOT onto sys.path)
python3 -m pytest tests/
python3 -m pytest tests/test_models.py::test_build_gan_models_forward_shapes   # single test
```

**Fast iteration:** the `--max-train-samples` / `--max-val-samples` / `--max-test-samples` caps (0 = full set) and small `--epochs` let you smoke-test the train chain quickly without touching the full 60k dataset.

**Data is not auto-downloaded.** `src/data.py` calls `FashionMNIST(..., download=False)`, so the dataset must already exist under `data/` (the `--data-root`). Tests that build dataloaders will fail without it.

## Architecture

`train.py` is the single training entry point; everything else composes around it.

- **`src/config.py`** — `TrainConfig` dataclass + argparse. `parse_config()` validates args and is the single source of all hyperparameters threaded through the rest of the code. Note: `--image-size` defaults to 28 when unset.
- **`src/data.py`** — builds `DataBundle` (train/val/test `DataLoader`s). Splits train into train/val via `--val-ratio` with a seeded generator. `WrappedFashionMNIST` wraps each sample into a `{"images", "labels"}` dict, and `collate_batch` keeps that dict shape — **the engine indexes `batch["images"]`, so any new dataset must preserve this contract.**
- **`src/models/`** — `gan.py` (MLP G/D, sigmoid output), `dcgan.py` (transpose-conv G / conv D, sigmoid output). `registry.py::build_model(name, **kwargs)` is the only constructor the rest of the code calls; `AVAILABLE_MODELS` in `constants.py` gates valid names.
- **`src/engine.py`** — `run_training()` is the full loop: standard two-step GAN update (D on real+detached-fake, then G), `BCELoss`, per-epoch val eval, checkpoint + sample-grid dump on improvement, final test eval on the reloaded best checkpoint, then writes all metric files.
- **`src/utils/`** — `paths.py` (`build_run_name`, the lr-tag encoding `0.0002`→`lr0p0002`), `io.py` (CSV/JSON/txt writers + `ensure_dir`), `plotting.py` (curves & grids), `profiling.py` (param counts), `runtime.py` (`set_seed`, `setup_matplotlib`).

### Two model-shape conventions you must respect

The GAN and DCGAN differ in tensor rank, and several places branch on `config.model == "dcgan"`:

1. **Noise shape** — vanilla GAN uses `(B, latent_dim)`; DCGAN uses `(B, latent_dim, 1, 1)`. Centralized in `engine.build_noise()` and duplicated in `scripts/generate_report_assets.py` (`build_noise` / `adapt_noise_for_model`).
2. **Discriminator output shape** — GAN D returns `(B, 1)`; DCGAN D returns `(B, 1, 1, 1)`. The engine handles this by rebuilding `real_labels`/`fake_labels` with `torch.ones_like(real_scores)` whenever `real_scores.dim() > 2`. Preserve this when editing the loss code.

### Checkpoint selection metric

Best-checkpoint selection does **not** minimize generator loss — it minimizes `compute_validation_score()` in `engine.py`, a balanced adversarial score (distance of G/D losses from their `log2` / `2log2` equilibria plus distance of D(real)/D(fake) from 0.5). This avoids picking mode-collapsed checkpoints. `sweep_lr.py` sorts runs by this `best_validation_score` to pick the best lr.

## Output layout

Each run writes to `outputs/<model>/<run_name>/`: `model_structure.txt`, `epoch_metrics.csv`, `summary_metrics.csv`, `run_metadata.json`, `best_model.pth`, `training_curves.png`, `generated_samples.png`. Sweeps additionally emit `outputs/<model>/<model>_<optimizer>_lr_sweep_summary.csv` and `_best_lr.txt`. Report assets land in `实验模板/fig/generated/`, `实验模板/tables/`, and `实验模板/generated_assets_manifest.txt`.

`run_metadata.json` is the bridge between stages: `sweep_lr.py` and `generate_report_assets.py` read it back to recover hyperparameters and reconstruct the generator via `build_model`, so keep new model hyperparameters in both the metadata written by `train.py` and the `build_model` kwargs.

## Notes

- `old/` holds the original tutorial notebooks/scripts (`gan-pytorch`, `dcgan_faces_tutorial`) the framework was refactored from — reference only, not imported.
- `src/models/registry.py` imports via absolute paths (`from src.models...`), so scripts must run with `lab4/` on `sys.path` (the entry scripts and tests handle this themselves).
- `setup_matplotlib(PROJECT_ROOT)` is called before importing `pyplot` to pin a writable config/cache dir (`.matplotlib/`) — keep that ordering when adding plotting code.
