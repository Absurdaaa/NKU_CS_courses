"""Data helpers for conditional name generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import unicodedata

import torch
from torch.utils.data import Dataset

from .constants import ALLOWED_CHARACTERS, NUM_CHARACTERS

# 生成任务里会额外用一个 EOS 结束标记，表示“名字到这里生成完了”
EOS_INDEX = NUM_CHARACTERS
GEN_OUTPUT_SIZE = NUM_CHARACTERS + 1


def unicode_to_ascii(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.strip())
    filtered = []
    for char in normalized:
        if unicodedata.category(char) == "Mn":
            continue
        filtered.append(char if char in ALLOWED_CHARACTERS else "_")
    return "".join(filtered)


def letter_to_index(letter: str) -> int:
    return ALLOWED_CHARACTERS.find(letter) if letter in ALLOWED_CHARACTERS else ALLOWED_CHARACTERS.find("_")


def category_tensor(category_index: int, num_categories: int) -> torch.Tensor:
    tensor = torch.zeros(1, num_categories, dtype=torch.float32)
    tensor[0, category_index] = 1.0
    return tensor


def input_tensor(line: str) -> torch.Tensor:
    # 输入序列不含 EOS，因为每一步是“根据当前字符预测下一个字符”
    tensor = torch.zeros(len(line), 1, NUM_CHARACTERS, dtype=torch.float32)
    for index, letter in enumerate(line):
        tensor[index, 0, letter_to_index(letter)] = 1.0
    return tensor


def target_tensor(line: str) -> torch.Tensor:
    # 目标序列从第二个字符开始，最后再补一个 EOS，表示名字结束
    target_indices = [letter_to_index(line[index]) for index in range(1, len(line))]
    target_indices.append(EOS_INDEX)
    return torch.tensor(target_indices, dtype=torch.long)


@dataclass
class NameGenerationSample:
    category_index: int
    category_name: str
    name: str


class NameGenerationDataset(Dataset[NameGenerationSample]):
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
        self.samples: list[NameGenerationSample] = []
        self.category_to_names: dict[str, list[str]] = {}

        for category_index, path in enumerate(text_files):
            names: list[str] = []
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                name = unicode_to_ascii(raw_line)
                if not name:
                    continue
                names.append(name)
                self.samples.append(
                    NameGenerationSample(
                        category_index=category_index,
                        category_name=path.stem,
                        name=name,
                    )
                )
            self.category_to_names[path.stem] = names

    def __len__(self) -> int:
        return len(self.samples)

    def random_sample(self, rng: random.Random) -> NameGenerationSample:
        return self.samples[rng.randrange(len(self.samples))]

    def __getitem__(self, index: int) -> NameGenerationSample:
        return self.samples[index]


def collate_generation_samples(batch: list[NameGenerationSample], num_categories: int) -> dict[str, torch.Tensor | list[str]]:
    # 这里把一批名字补到同样长度；损失里会忽略 padding 对应的位置
    batch_size = len(batch)
    lengths = torch.tensor([len(sample.name) for sample in batch], dtype=torch.long)
    max_length = int(lengths.max().item())

    categories = torch.zeros(batch_size, num_categories, dtype=torch.float32)
    inputs = torch.zeros(max_length, batch_size, NUM_CHARACTERS, dtype=torch.float32)
    targets = torch.full((max_length, batch_size), fill_value=-100, dtype=torch.long)
    category_names: list[str] = []
    names: list[str] = []

    for batch_index, sample in enumerate(batch):
        categories[batch_index, sample.category_index] = 1.0
        input_seq = input_tensor(sample.name).squeeze(1)
        target_seq = target_tensor(sample.name)
        seq_len = input_seq.size(0)
        inputs[:seq_len, batch_index, :] = input_seq
        targets[: target_seq.size(0), batch_index] = target_seq
        category_names.append(sample.category_name)
        names.append(sample.name)

    return {
        "categories": categories,
        "inputs": inputs,
        "targets": targets,
        "lengths": lengths,
        "category_names": category_names,
        "names": names,
    }
