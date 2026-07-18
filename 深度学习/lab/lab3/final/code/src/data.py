"""Dataset and dataloader utilities for translation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import re
import unicodedata

import torch
from torch.utils.data import DataLoader, Dataset, random_split

from .config import ExperimentConfig
from .constants import ENGLISH_PREFIXES, EOS_TOKEN, PAD_TOKEN, SOS_TOKEN, SPECIAL_TOKENS, UNK_TOKEN


@dataclass
class TranslationSample:
    source_text: str
    target_text: str
    source_ids: list[int]
    target_ids: list[int]


class LanguageVocabulary:
    def __init__(self, name: str) -> None:
        self.name = name
        self.word2index = dict(SPECIAL_TOKENS)
        self.word2count: dict[str, int] = {}
        self.index2word = {index: token for token, index in SPECIAL_TOKENS.items()}
        self.size = len(SPECIAL_TOKENS)
        self.pad_idx = PAD_TOKEN
        self.sos_idx = SOS_TOKEN
        self.eos_idx = EOS_TOKEN
        self.unk_idx = UNK_TOKEN

    def add_sentence(self, sentence: str) -> None:
        for word in sentence.split(" "):
            self.add_word(word)

    def add_word(self, word: str) -> None:
        if word not in self.word2index:
            self.word2index[word] = self.size
            self.index2word[self.size] = word
            self.word2count[word] = 1
            self.size += 1
            return
        self.word2count[word] = self.word2count.get(word, 0) + 1

    def encode(self, sentence: str) -> list[int]:
        tokens = [self.word2index.get(word, self.unk_idx) for word in sentence.split(" ")]
        return [self.sos_idx] + tokens + [self.eos_idx]

    def decode(self, token_ids: list[int], stop_at_eos: bool = True) -> str:
        words: list[str] = []
        for token_id in token_ids:
            if token_id == self.pad_idx or token_id == self.sos_idx:
                continue
            if token_id == self.eos_idx and stop_at_eos:
                break
            words.append(self.index2word.get(token_id, "<UNK>"))
        return " ".join(words)


def unicode_to_ascii(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )


def normalize_string(text: str) -> str:
    text = unicode_to_ascii(text.lower().strip())
    text = re.sub(r"([.!?])", r" \1", text)
    text = re.sub(r"[^a-zA-Z.!?]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def filter_pair(source: str, target: str, config: ExperimentConfig) -> bool:
    source_len = len(source.split(" "))
    target_len = len(target.split(" "))
    if source_len >= config.max_length or target_len >= config.max_length:
        return False
    if config.filter_english_prefixes and not any(target.startswith(prefix) for prefix in ENGLISH_PREFIXES):
        return False
    return True


def read_parallel_pairs(config: ExperimentConfig) -> tuple[LanguageVocabulary, LanguageVocabulary, list[tuple[str, str]]]:
    if not config.data_root.exists():
        raise FileNotFoundError(
            f"Parallel corpus not found: {config.data_root}. Place eng-fra.txt under lab3/data/."
        )

    lines = config.data_root.read_text(encoding="utf-8").strip().splitlines()
    raw_pairs: list[tuple[str, str]] = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        english = normalize_string(parts[0])
        french = normalize_string(parts[1])
        pair = (french, english) if config.reverse_translation else (english, french)
        raw_pairs.append(pair)

    filtered_pairs = [pair for pair in raw_pairs if filter_pair(pair[0], pair[1], config)]
    if config.max_samples > 0:
        filtered_pairs = filtered_pairs[: config.max_samples]

    input_lang = LanguageVocabulary("fra" if config.reverse_translation else "eng")
    output_lang = LanguageVocabulary("eng" if config.reverse_translation else "fra")
    for source, target in filtered_pairs:
        input_lang.add_sentence(source)
        output_lang.add_sentence(target)
    return input_lang, output_lang, filtered_pairs


class TranslationDataset(Dataset[TranslationSample]):
    def __init__(self, input_lang: LanguageVocabulary, output_lang: LanguageVocabulary, pairs: list[tuple[str, str]]) -> None:
        self.samples = [
            TranslationSample(
                source_text=source,
                target_text=target,
                source_ids=input_lang.encode(source),
                target_ids=output_lang.encode(target),
            )
            for source, target in pairs
        ]

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> TranslationSample:
        return self.samples[index]


def pad_sequences(sequences: list[list[int]], pad_idx: int) -> tuple[torch.Tensor, torch.Tensor]:
    lengths = torch.tensor([len(sequence) for sequence in sequences], dtype=torch.long)
    max_length = int(lengths.max().item())
    tensor = torch.full((len(sequences), max_length), fill_value=pad_idx, dtype=torch.long)
    for index, sequence in enumerate(sequences):
        tensor[index, : len(sequence)] = torch.tensor(sequence, dtype=torch.long)
    return tensor, lengths


def build_collate_fn(input_lang: LanguageVocabulary, output_lang: LanguageVocabulary):
    def collate(batch: list[TranslationSample]) -> dict[str, object]:
        batch = sorted(batch, key=lambda item: len(item.source_ids), reverse=True)
        source_tensor, source_lengths = pad_sequences([item.source_ids for item in batch], input_lang.pad_idx)
        target_tensor, target_lengths = pad_sequences([item.target_ids for item in batch], output_lang.pad_idx)
        return {
            "source_tokens": source_tensor,
            "source_lengths": source_lengths,
            "target_tokens": target_tensor,
            "target_lengths": target_lengths,
            "source_texts": [item.source_text for item in batch],
            "target_texts": [item.target_text for item in batch],
        }

    return collate


@dataclass
class TranslationDataBundle:
    train_loader: DataLoader
    val_loader: DataLoader
    test_loader: DataLoader
    input_vocab: LanguageVocabulary
    output_vocab: LanguageVocabulary
    raw_pairs: list[tuple[str, str]]


def build_dataloaders(config: ExperimentConfig) -> TranslationDataBundle:
    input_lang, output_lang, pairs = read_parallel_pairs(config)
    dataset = TranslationDataset(input_lang, output_lang, pairs)

    total_size = len(dataset)
    train_size = int(total_size * config.train_ratio)
    val_size = int(total_size * config.val_ratio)
    test_size = total_size - train_size - val_size
    if min(train_size, val_size, test_size) <= 0:
        raise ValueError("Current split ratios produce an empty split. Adjust train_ratio/val_ratio.")

    generator = torch.Generator().manual_seed(config.seed)
    train_set, val_set, test_set = random_split(dataset, [train_size, val_size, test_size], generator=generator)

    collate_fn = build_collate_fn(input_lang, output_lang)
    common_args = {
        "batch_size": config.batch_size,
        "num_workers": config.num_workers,
        "collate_fn": collate_fn,
        "pin_memory": config.device.type == "cuda",
    }
    train_loader = DataLoader(train_set, shuffle=True, **common_args)
    val_loader = DataLoader(val_set, shuffle=False, **common_args)
    test_loader = DataLoader(test_set, shuffle=False, **common_args)
    return TranslationDataBundle(
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        input_vocab=input_lang,
        output_vocab=output_lang,
        raw_pairs=pairs,
    )


def sample_pairs_for_preview(pairs: list[tuple[str, str]], limit: int, seed: int) -> list[tuple[str, str]]:
    random_generator = random.Random(seed)
    if len(pairs) <= limit:
        return pairs
    return random_generator.sample(pairs, k=limit)
