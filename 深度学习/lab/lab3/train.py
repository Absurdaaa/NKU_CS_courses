#!/usr/bin/env python3
"""Project entrypoint for lab3 sequence-to-sequence experiments."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

from src.utils.runtime import set_seed, setup_matplotlib

setup_matplotlib(PROJECT_ROOT)

from src.config import parse_config
from src.data import build_dataloaders
from src.engine import run_training
from src.models import build_model
from src.utils.io import ensure_dir, save_model_summary, save_run_metadata
from src.utils.paths import build_run_name


def main() -> None:
    config = parse_config(PROJECT_ROOT)
    set_seed(config.seed)

    output_dir = config.output_dir / config.model / build_run_name(config)
    ensure_dir(output_dir)

    dataloaders = build_dataloaders(config)
    model = build_model(
        model_name=config.model,
        src_vocab_size=dataloaders.input_vocab.size,
        tgt_vocab_size=dataloaders.output_vocab.size,
        hidden_size=config.hidden_size,
        num_layers=config.num_layers,
        dropout=config.dropout,
        pad_idx=dataloaders.output_vocab.pad_idx,
        max_decode_length=config.max_length + 1,
    ).to(config.device)

    print(f"Using device: {config.device}")
    print(f"Run name: {output_dir.name}")
    print(f"Train size: {len(dataloaders.train_loader.dataset)}")
    print(f"Val size: {len(dataloaders.val_loader.dataset)}")
    print(f"Test size: {len(dataloaders.test_loader.dataset)}")
    print("\nModel structure:\n")
    print(model)

    save_model_summary(model, str(config.device), output_dir / "model_structure.txt")
    save_run_metadata(
        {
            "model": config.model,
            "run_name": output_dir.name,
            "epochs": config.epochs,
            "batch_size": config.batch_size,
            "optimizer": config.optimizer,
            "lr": config.lr,
            "hidden_size": config.hidden_size,
            "num_layers": config.num_layers,
            "dropout": config.dropout,
            "teacher_forcing_ratio": config.teacher_forcing_ratio,
            "scheduled_sampling": config.scheduled_sampling,
            "scheduled_sampling_strategy": config.scheduled_sampling_strategy,
            "scheduled_sampling_min_ratio": config.scheduled_sampling_min_ratio,
            "scheduled_sampling_decay_epochs": config.scheduled_sampling_decay_epochs,
            "scheduled_sampling_inverse_sigmoid_k": config.scheduled_sampling_inverse_sigmoid_k,
            "seed": config.seed,
            "device": str(config.device),
            "max_length": config.max_length,
            "max_samples": config.max_samples,
            "reverse_translation": config.reverse_translation,
            "filter_english_prefixes": config.filter_english_prefixes,
            "train_size": len(dataloaders.train_loader.dataset),
            "val_size": len(dataloaders.val_loader.dataset),
            "test_size": len(dataloaders.test_loader.dataset),
            "source_vocab_size": dataloaders.input_vocab.size,
            "target_vocab_size": dataloaders.output_vocab.size,
            "source_lang": dataloaders.input_vocab.name,
            "target_lang": dataloaders.output_vocab.name,
            "attention_score_method": getattr(model, "score_method", None),
        },
        output_dir / "run_metadata.json",
    )

    summary = run_training(
        model=model,
        dataloaders=dataloaders,
        config=config,
        output_dir=output_dir,
    )

    print(f"\nSaved outputs to: {output_dir}")
    print(f"- model structure: {output_dir / 'model_structure.txt'}")
    print(f"- epoch logs: {output_dir / 'epoch_metrics.csv'}")
    print(f"- summary metrics: {output_dir / 'summary_metrics.csv'}")
    print(f"- run metadata: {output_dir / 'run_metadata.json'}")
    print(f"- training curves: {output_dir / 'training_curves.png'}")
    print(f"- sample translations: {output_dir / 'sample_translations.csv'}")
    print(f"- best checkpoint: {output_dir / 'best_model.pth'}")
    print(f"- final test acc: {summary['test_acc']:.4f}")
    print(f"- final test exact match: {summary['test_exact_match']:.4f}")


if __name__ == "__main__":
    main()
