"""Training and sampling helpers for conditional name generation."""

from __future__ import annotations

import random
import time
import csv

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Subset

from .generation_config import GenerationConfig
from .generation_data import (
    ALLOWED_CHARACTERS,
    EOS_INDEX,
    NameGenerationDataset,
    category_tensor,
    collate_generation_samples,
    input_tensor,
)
from .utils.io import save_epoch_metrics, save_summary_metrics


def resolve_sample_categories(dataset: NameGenerationDataset, config: GenerationConfig) -> list[str]:
    if config.sample_categories.strip().lower() == "all":
        return list(dataset.class_names)

    requested = [item.strip() for item in config.sample_categories.split(",") if item.strip()]
    valid = [item for item in requested if item in dataset.class_names]
    return valid if valid else [name for name in ("Russian", "German", "Spanish", "Chinese") if name in dataset.class_names]


def build_start_letter_pool(dataset: NameGenerationDataset, category_name: str) -> list[str]:
    # 优先从该语言训练名字中真实出现过的首字母里抽样，避免固定几个字母太单一
    initials = [name[0] for name in dataset.category_to_names.get(category_name, []) if name]
    initials = [char for char in initials if char in ALLOWED_CHARACTERS and char.isalpha()]
    if initials:
        return initials
    fallback = category_name[0].upper() if category_name else "A"
    return [fallback]


def build_optimizer(model: nn.Module, config: GenerationConfig) -> torch.optim.Optimizer:
    if config.optimizer == "sgd":
        return torch.optim.SGD(model.parameters(), lr=config.lr, momentum=0.9)
    if config.optimizer == "adamw":
        return torch.optim.AdamW(model.parameters(), lr=config.lr)
    return torch.optim.Adam(model.parameters(), lr=config.lr)


def _select_active_state(state, next_state, active_mask: torch.Tensor):
    # 短名字结束后，不再继续更新它的循环状态
    if isinstance(state, tuple):
        hidden, cell = state
        next_hidden, next_cell = next_state
        active = active_mask.view(1, -1, 1)
        hidden = torch.where(active, next_hidden, hidden)
        cell = torch.where(active, next_cell, cell)
        return hidden, cell
    active = active_mask.view(-1, 1)
    return torch.where(active, next_state, state)


def train_one_batch(
    model: nn.Module,
    batch: dict[str, torch.Tensor | list[str]],
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    config: GenerationConfig,
) -> float:
    categories = batch["categories"].to(config.device)
    inputs = batch["inputs"].to(config.device)
    targets = batch["targets"].to(config.device)
    lengths = batch["lengths"].to(config.device)
    batch_size = categories.size(0)
    hidden = model.init_state(config.device, batch_size=batch_size)

    optimizer.zero_grad()
    total_loss = 0.0

    for step_index in range(inputs.size(0)):
        output, next_hidden = model(categories, inputs[step_index], hidden)
        step_loss = criterion(output, targets[step_index])
        total_loss = total_loss + step_loss
        active = step_index < lengths
        hidden = _select_active_state(hidden, next_hidden, active)

    total_loss.backward()
    # 这个任务本质上也是序列模型，必要时也可以开梯度裁剪稳一下
    if config.clip_grad_norm > 0:
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=config.clip_grad_norm)
    optimizer.step()
    token_count = int((targets != -100).sum().item())
    return float(total_loss.item() / max(token_count, 1))


def sample_name(
    model: nn.Module,
    category_index: int,
    num_categories: int,
    start_letter: str,
    config: GenerationConfig,
) -> str:
    model.eval()
    with torch.no_grad():
        category = category_tensor(category_index, num_categories).to(config.device)
        current_input = input_tensor(start_letter).to(config.device)
        hidden = model.init_state(config.device, batch_size=1)
        output_name = start_letter

        for _ in range(config.sample_max_length):
            output, hidden = model(category, current_input[0], hidden)
            top_index = int(output.topk(1).indices[0, 0].item())
            if top_index == EOS_INDEX:
                break
            letter = ALLOWED_CHARACTERS[top_index]
            output_name += letter
            current_input = input_tensor(letter).to(config.device)

    model.train()
    return output_name


def save_generated_samples(path, generated_samples: dict[str, list[str]]) -> None:
    lines: list[str] = []
    for category_name, samples in generated_samples.items():
        lines.append(f"[{category_name}]")
        lines.extend(samples)
        lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def save_generated_metrics(path, rows: list[dict[str, float | int | str]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_generated_metrics(dataset: NameGenerationDataset, generated_samples: dict[str, list[str]]):
    rows: list[dict[str, float | int | str]] = []
    for category_name, samples in generated_samples.items():
        if not samples:
            continue
        train_set = set(dataset.category_to_names.get(category_name, []))
        unique_count = len(set(samples))
        overlap_count = sum(1 for sample in samples if sample in train_set)
        avg_length = sum(len(sample) for sample in samples) / len(samples)
        rows.append(
            {
                "category_name": category_name,
                "generated_count": len(samples),
                "avg_generated_length": avg_length,
                "unique_ratio": unique_count / len(samples),
                "train_overlap_ratio": overlap_count / len(samples),
            }
        )
    return rows


def run_generation_training(
    model: nn.Module,
    dataset: NameGenerationDataset,
    config: GenerationConfig,
    output_dir,
):
    criterion = nn.NLLLoss(ignore_index=-100)
    optimizer = build_optimizer(model, config)
    rng = random.Random(config.seed)
    history: list[dict[str, float | int]] = []
    best_epoch = 0
    best_loss = float("inf")
    best_state = None
    start_time = time.time()

    sample_indices = list(range(len(dataset.samples)))
    for epoch in range(1, config.epochs + 1):
        rng.shuffle(sample_indices)
        epoch_indices = sample_indices
        if config.max_samples_per_epoch > 0:
            epoch_indices = sample_indices[: config.max_samples_per_epoch]
        epoch_dataset = Subset(dataset, epoch_indices)
        train_loader = DataLoader(
            epoch_dataset,
            batch_size=config.batch_size,
            shuffle=False,
            num_workers=0,
            collate_fn=lambda batch: collate_generation_samples(batch, len(dataset.class_names)),
            pin_memory=config.device.type == "cuda",
        )
        epoch_start = time.time()
        total_loss = 0.0
        batch_count = 0

        for batch in train_loader:
            total_loss += train_one_batch(
                model=model,
                batch=batch,
                criterion=criterion,
                optimizer=optimizer,
                config=config,
            )
            batch_count += 1

        avg_loss = total_loss / max(batch_count, 1)
        epoch_time = time.time() - epoch_start
        elapsed_time = time.time() - start_time
        history.append(
            {
                "epoch": epoch,
                "train_loss": avg_loss,
                "epoch_time_sec": epoch_time,
                "elapsed_train_time_sec": elapsed_time,
            }
        )
        print(f"Epoch [{epoch}/{config.epochs}] train_loss={avg_loss:.4f}")

        if avg_loss < best_loss:
            best_loss = avg_loss
            best_epoch = epoch
            best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
            torch.save(best_state, output_dir / "best_model.pth")

    if best_state is None:
        raise RuntimeError("Generation training did not produce a checkpoint.")

    model.load_state_dict(best_state)
    total_time = time.time() - start_time
    summary = {
        "best_train_loss": best_loss,
        "best_epoch": best_epoch,
        "final_train_loss": history[-1]["train_loss"],
        "total_train_time_sec": total_time,
        "avg_epoch_time_sec": total_time / max(config.epochs, 1),
        "sample_count": len(dataset.samples),
        "batch_size": config.batch_size,
        "max_samples_per_epoch": config.max_samples_per_epoch if config.max_samples_per_epoch > 0 else len(dataset.samples),
        "class_count": len(dataset.class_names),
    }

    generated_samples: dict[str, list[str]] = {}
    for category_name in resolve_sample_categories(dataset, config):
        if category_name not in dataset.class_names:
            continue
        category_index = dataset.class_names.index(category_name)
        start_letter_pool = build_start_letter_pool(dataset, category_name)
        generated_samples[category_name] = []
        for _ in range(config.samples_per_category):
            start_letter = rng.choice(start_letter_pool)
            generated_samples[category_name].append(
                sample_name(model, category_index, len(dataset.class_names), start_letter, config)
            )

    save_epoch_metrics(history, output_dir / "epoch_metrics.csv")
    save_summary_metrics(summary, output_dir / "summary_metrics.csv")
    save_generated_samples(output_dir / "generated_samples.txt", generated_samples)
    save_generated_metrics(output_dir / "generated_metrics.csv", build_generated_metrics(dataset, generated_samples))
    return history, summary, generated_samples
