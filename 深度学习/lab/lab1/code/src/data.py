"""Dataset and dataloader utilities."""

from __future__ import annotations

import tarfile
from pathlib import Path
from typing import Tuple

import torch
from torch.utils.data import DataLoader, Subset
import torchvision
import torchvision.transforms as transforms

from .config import ExperimentConfig


def prepare_cifar10_data(data_root: Path) -> None:
    extracted_dir = data_root / "cifar-10-batches-py"
    archive_path = data_root / "cifar-10-python.tar.gz"

    if extracted_dir.exists():
        return
    if archive_path.exists():
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=data_root)


def build_dataloaders(
    config: ExperimentConfig,
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    train_transform = transforms.Compose(
        [
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )
    eval_transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )

    config.data_root.mkdir(parents=True, exist_ok=True)
    prepare_cifar10_data(config.data_root)

    train_dataset = torchvision.datasets.CIFAR10(
        root=str(config.data_root),
        train=True,
        download=config.download,
        transform=train_transform,
    )
    val_dataset = torchvision.datasets.CIFAR10(
        root=str(config.data_root),
        train=True,
        download=False,
        transform=eval_transform,
    )
    test_dataset = torchvision.datasets.CIFAR10(
        root=str(config.data_root),
        train=False,
        download=config.download,
        transform=eval_transform,
    )

    val_size = int(len(train_dataset) * config.val_ratio)
    train_size = len(train_dataset) - val_size
    indices = torch.randperm(
        len(train_dataset), generator=torch.Generator().manual_seed(config.seed)
    ).tolist()
    train_indices = indices[:train_size]
    val_indices = indices[train_size:]

    train_subset = Subset(train_dataset, train_indices)
    val_subset = Subset(val_dataset, val_indices)

    loader_kwargs = {
        "batch_size": config.batch_size,
        "num_workers": config.num_workers,
        "pin_memory": torch.cuda.is_available(),
    }
    train_loader = DataLoader(train_subset, shuffle=True, **loader_kwargs)
    val_loader = DataLoader(val_subset, shuffle=False, **loader_kwargs)
    test_loader = DataLoader(test_dataset, shuffle=False, **loader_kwargs)
    return train_loader, val_loader, test_loader
