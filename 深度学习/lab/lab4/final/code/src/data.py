"""FashionMNIST 数据读取与 dataloader 构建。"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch.utils.data import DataLoader, Dataset, Subset, random_split
from torchvision.datasets import FashionMNIST
from torchvision.transforms import Compose, Normalize, Resize, ToTensor

from .config import TrainConfig
from .constants import FASHION_MNIST_CLASS_NAMES


@dataclass(slots=True)
class DataBundle:
    """训练/验证/测试 dataloader 打包。"""

    train_loader: DataLoader
    val_loader: DataLoader
    test_loader: DataLoader
    class_names: tuple[str, ...]


class WrappedFashionMNIST(Dataset):
    """把 torchvision 样本包装成统一的 dict 结构。"""

    def __init__(self, dataset: Dataset) -> None:
        self.dataset = dataset

    def __len__(self) -> int:
        return len(self.dataset)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor | int]:
        image, label = self.dataset[index]
        return {"images": image, "labels": label}


def build_transform(image_size: int) -> Compose:
    return Compose(
        [
            Resize((image_size, image_size)),
            ToTensor(),
            Normalize((0.5,), (0.5,)),
        ]
    )


def maybe_limit_subset(dataset: Dataset, max_samples: int, seed: int) -> Dataset:
    if max_samples <= 0 or len(dataset) <= max_samples:
        return dataset
    generator = torch.Generator().manual_seed(seed)
    indices = torch.randperm(len(dataset), generator=generator)[:max_samples].tolist()
    return Subset(dataset, indices)


def collate_batch(batch: list[dict[str, torch.Tensor | int]]) -> dict[str, torch.Tensor]:
    images = torch.stack([item["images"] for item in batch])
    labels = torch.tensor([int(item["labels"]) for item in batch], dtype=torch.long)
    return {"images": images, "labels": labels}


def build_dataloaders(config: TrainConfig) -> DataBundle:
    transform = build_transform(config.image_size)
    train_dataset_full = FashionMNIST(root=str(config.data_root), train=True, transform=transform, download=False)
    test_dataset_full = FashionMNIST(root=str(config.data_root), train=False, transform=transform, download=False)

    val_size = int(len(train_dataset_full) * config.val_ratio)
    train_size = len(train_dataset_full) - val_size
    if min(train_size, val_size) <= 0:
        raise ValueError("Current val_ratio produces an empty train or val split.")

    split_generator = torch.Generator().manual_seed(config.seed)
    train_dataset, val_dataset = random_split(
        train_dataset_full,
        [train_size, val_size],
        generator=split_generator,
    )

    train_dataset = WrappedFashionMNIST(maybe_limit_subset(train_dataset, config.max_train_samples, config.seed))
    val_dataset = WrappedFashionMNIST(maybe_limit_subset(val_dataset, config.max_val_samples, config.seed + 1))
    test_dataset = WrappedFashionMNIST(maybe_limit_subset(test_dataset_full, config.max_test_samples, config.seed + 2))

    loader_args = {
        "batch_size": config.batch_size,
        "num_workers": config.num_workers,
        "pin_memory": config.device.type == "cuda",
        "collate_fn": collate_batch,
    }
    train_generator = torch.Generator().manual_seed(config.seed)
    train_loader = DataLoader(train_dataset, shuffle=True, generator=train_generator, **loader_args)
    val_loader = DataLoader(val_dataset, shuffle=False, **loader_args)
    test_loader = DataLoader(test_dataset, shuffle=False, **loader_args)
    return DataBundle(
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        class_names=FASHION_MNIST_CLASS_NAMES,
    )
