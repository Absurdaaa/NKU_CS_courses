"""Dataset and dataloader utilities for name classification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unicodedata

import torch
from torch.utils.data import DataLoader, Dataset, random_split

from .config import ExperimentConfig
from .constants import ALLOWED_CHARACTERS, NUM_CHARACTERS


def unicode_to_ascii(text: str) -> str:
    # 先做 Unicode 标准化，再去掉重音符号；不在词表中的字符统一映射为 "_"
    normalized = unicodedata.normalize("NFD", text.strip())
    filtered = []
    for char in normalized:
        if unicodedata.category(char) == "Mn":
            continue
        filtered.append(char if char in ALLOWED_CHARACTERS else "_")
    return "".join(filtered)


def letter_to_index(letter: str) -> int:
    return ALLOWED_CHARACTERS.find(letter) if letter in ALLOWED_CHARACTERS else ALLOWED_CHARACTERS.find("_")


def line_to_tensor(line: str) -> torch.Tensor:
    # 把名字编码成 [seq_len, num_characters] 的 one-hot 序列
    tensor = torch.zeros(len(line), NUM_CHARACTERS, dtype=torch.float32)
    for index, letter in enumerate(line):
        tensor[index, letter_to_index(letter)] = 1.0
    return tensor


@dataclass
class NameSample:
    label_index: int
    label_name: str
    name: str
    sequence: torch.Tensor


class NamesDataset(Dataset[NameSample]):
    def __init__(self, data_root: Path) -> None:
        if not data_root.exists():
            raise FileNotFoundError(
                f"Dataset directory not found: {data_root}. "
                "Place the language name files under data/names/."
            )

        text_files = sorted(data_root.glob("*.txt"))
        if not text_files:
            raise FileNotFoundError(f"No .txt files found in {data_root}.")

        self.class_names = [path.stem for path in text_files]
        self.samples: list[NameSample] = []

        for label_index, path in enumerate(text_files):
            # 每个 txt 文件对应一个类别，文件中的每一行是一个名字样本
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                name = unicode_to_ascii(raw_line)
                if not name:
                    continue
                self.samples.append(
                    NameSample(
                        label_index=label_index,
                        label_name=path.stem,
                        name=name,
                        sequence=line_to_tensor(name),
                    )
                )

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> NameSample:
        return self.samples[index]


def collate_names(batch: list[NameSample]) -> dict[str, object]:
    # pack_padded_sequence 要求按长度降序排列，这里在组 batch 时一次性处理
    batch = sorted(batch, key=lambda item: item.sequence.size(0), reverse=True)
    lengths = torch.tensor([item.sequence.size(0) for item in batch], dtype=torch.long)
    max_length = int(lengths.max().item())
    batch_size = len(batch)

    sequences = torch.zeros(max_length, batch_size, NUM_CHARACTERS, dtype=torch.float32)
    labels = torch.tensor([item.label_index for item in batch], dtype=torch.long)
    names = []
    label_names = []

    for batch_index, item in enumerate(batch):
        seq_len = item.sequence.size(0)
        # 不足 max_length 的尾部保持 0，相当于 padding
        sequences[:seq_len, batch_index, :] = item.sequence
        names.append(item.name)
        label_names.append(item.label_name)

    return {
        "sequences": sequences,
        "lengths": lengths,
        "labels": labels,
        "names": names,
        "label_names": label_names,
    }


def build_dataloaders(config: ExperimentConfig):
    dataset = NamesDataset(config.data_root)

    total_size = len(dataset)
    train_size = int(total_size * config.train_ratio)
    val_size = int(total_size * config.val_ratio)
    test_size = total_size - train_size - val_size
    if min(train_size, val_size, test_size) <= 0:
        raise ValueError("Current split ratios produce an empty split. Adjust train_ratio/val_ratio.")

    # 固定随机种子，保证 train/val/test 划分可复现
    generator = torch.Generator().manual_seed(config.seed)
    train_set, val_set, test_set = random_split(dataset, [train_size, val_size, test_size], generator=generator)

    common_args = {
        "batch_size": config.batch_size,
        "num_workers": config.num_workers,
        "collate_fn": collate_names,
        "pin_memory": config.device.type == "cuda",
    }
    train_loader = DataLoader(train_set, shuffle=True, **common_args)
    val_loader = DataLoader(val_set, shuffle=False, **common_args)
    test_loader = DataLoader(test_set, shuffle=False, **common_args)
    return train_loader, val_loader, test_loader, dataset.class_names
