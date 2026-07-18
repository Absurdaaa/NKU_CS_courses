#!/usr/bin/env python3
"""Project entrypoint for name classification experiments."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

from src.config import parse_config
from src.data import build_dataloaders
from src.engine import run_training
from src.models import build_model
from src.utils.io import ensure_dir, save_model_summary, save_run_metadata
from src.utils.paths import build_run_name
from src.utils.runtime import set_seed, setup_matplotlib


def main() -> None:
    config = parse_config(PROJECT_ROOT)
    setup_matplotlib(PROJECT_ROOT)
    set_seed(config.seed)
    from src.utils.plotting import save_confusion_matrix, save_curves, save_gradient_norms

    output_dir = config.output_dir / config.model / build_run_name(config)
    ensure_dir(output_dir)

    train_loader, val_loader, test_loader, class_names = build_dataloaders(config)
    model = build_model(
        model_name=config.model,
        input_size=config.input_size,
        hidden_size=config.hidden_size,
        output_size=len(class_names),
        num_layers=config.num_layers,
        dropout=config.dropout,
    ).to(config.device)

    print(f"Using device: {config.device}")
    print(f"Run name: {output_dir.name}")
    print(f"Train size: {len(train_loader.dataset)}")
    print(f"Val size: {len(val_loader.dataset)}")
    print(f"Test size: {len(test_loader.dataset)}")
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
            "clip_grad_norm": config.clip_grad_norm,
            "hidden_size": config.hidden_size,
            "num_layers": config.num_layers,
            "dropout": config.dropout,
            "seed": config.seed,
            "device": str(config.device),
            "train_size": len(train_loader.dataset),
            "val_size": len(val_loader.dataset),
            "test_size": len(test_loader.dataset),
            "class_count": len(class_names),
            "class_names": class_names,
        },
        output_dir / "run_metadata.json",
    )
    history, gradient_history, val_confusion, test_confusion, summary = run_training(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        class_names=class_names,
        config=config,
        output_dir=output_dir,
    )

    save_curves(history, output_dir / "training_curves.png")
    save_gradient_norms(gradient_history, output_dir / "gradient_norms.png")
    save_confusion_matrix(val_confusion, class_names, output_dir / "val_confusion_matrix.png", "Validation Confusion Matrix")
    save_confusion_matrix(test_confusion, class_names, output_dir / "test_confusion_matrix.png", "Test Confusion Matrix")

    print(f"\nSaved outputs to: {output_dir}")
    print(f"- model structure: {output_dir / 'model_structure.txt'}")
    print(f"- epoch logs: {output_dir / 'epoch_metrics.csv'}")
    print(f"- gradient logs: {output_dir / 'gradient_metrics.csv'}")
    print(f"- summary metrics: {output_dir / 'summary_metrics.csv'}")
    print(f"- run metadata: {output_dir / 'run_metadata.json'}")
    print(f"- training curves: {output_dir / 'training_curves.png'}")
    print(f"- gradient curves: {output_dir / 'gradient_norms.png'}")
    print(f"- validation confusion: {output_dir / 'val_confusion_matrix.png'}")
    print(f"- test confusion: {output_dir / 'test_confusion_matrix.png'}")
    print(f"- class accuracy: {output_dir / 'class_accuracy.csv'}")
    print(f"- length-group accuracy: {output_dir / 'length_group_accuracy.csv'}")
    print(f"- best checkpoint: {output_dir / 'best_model.pth'}")
    print(f"- final test acc: {summary['test_acc']:.4f}")


if __name__ == "__main__":
    main()
