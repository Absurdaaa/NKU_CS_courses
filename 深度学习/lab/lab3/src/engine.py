"""Training and evaluation loops."""

from __future__ import annotations

from collections.abc import Iterable
import math
import time

import torch
import torch.nn as nn

from .config import ExperimentConfig
from .constants import EOS_TOKEN, PAD_TOKEN
from .data import LanguageVocabulary, TranslationDataBundle
from .utils.io import (
    ensure_dir,
    save_attention_rows,
    save_epoch_metrics,
    save_rows,
    save_summary_metrics,
    save_translation_samples,
)
from .utils.plotting import save_attention_heatmap, save_curves
from .utils.profiling import count_parameters, estimate_flops_per_sample, measure_inference_time


def build_optimizer(model: nn.Module, config: ExperimentConfig) -> torch.optim.Optimizer:
    if config.optimizer == "sgd":
        return torch.optim.SGD(model.parameters(), lr=config.lr, momentum=0.9)
    if config.optimizer == "adamw":
        return torch.optim.AdamW(model.parameters(), lr=config.lr)
    return torch.optim.Adam(model.parameters(), lr=config.lr)


def move_batch_to_device(batch: dict[str, object], device: torch.device) -> dict[str, object]:
    return {
        "source_tokens": batch["source_tokens"].to(device),
        "source_lengths": batch["source_lengths"].to(device),
        "target_tokens": batch["target_tokens"].to(device),
        "target_lengths": batch["target_lengths"].to(device),
        "source_texts": batch["source_texts"],
        "target_texts": batch["target_texts"],
    }


def sequence_cross_entropy(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    criterion = nn.CrossEntropyLoss(ignore_index=PAD_TOKEN)
    return criterion(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))


def trim_at_eos(token_ids: list[int]) -> list[int]:
    trimmed: list[int] = []
    for token_id in token_ids:
        if token_id == PAD_TOKEN:
            continue
        trimmed.append(token_id)
        if token_id == EOS_TOKEN:
            break
    return trimmed


def compute_sequence_metrics(predictions: torch.Tensor, targets: torch.Tensor) -> tuple[float, float]:
    mask = targets != PAD_TOKEN
    if mask.sum().item() == 0:
        return 0.0, 0.0

    token_accuracy = ((predictions == targets) & mask).sum().item() / mask.sum().item()

    exact_matches = 0
    for predicted_row, target_row in zip(predictions.detach().cpu().tolist(), targets.detach().cpu().tolist()):
        if trim_at_eos(predicted_row) == trim_at_eos(target_row):
            exact_matches += 1
    exact_match = exact_matches / max(targets.size(0), 1)
    return token_accuracy, exact_match


def compute_bleu_score(predictions: list[str], references: list[str], max_n: int = 4) -> float:
    if not predictions or not references or len(predictions) != len(references):
        return 0.0

    clipped_totals = [0 for _ in range(max_n)]
    prediction_totals = [0 for _ in range(max_n)]
    prediction_length = 0
    reference_length = 0

    for prediction, reference in zip(predictions, references):
        pred_tokens = prediction.split()
        ref_tokens = reference.split()
        prediction_length += len(pred_tokens)
        reference_length += len(ref_tokens)

        for n in range(1, max_n + 1):
            pred_ngrams: dict[tuple[str, ...], int] = {}
            ref_ngrams: dict[tuple[str, ...], int] = {}
            for i in range(max(len(pred_tokens) - n + 1, 0)):
                ngram = tuple(pred_tokens[i : i + n])
                pred_ngrams[ngram] = pred_ngrams.get(ngram, 0) + 1
            for i in range(max(len(ref_tokens) - n + 1, 0)):
                ngram = tuple(ref_tokens[i : i + n])
                ref_ngrams[ngram] = ref_ngrams.get(ngram, 0) + 1

            prediction_totals[n - 1] += max(len(pred_tokens) - n + 1, 0)
            for ngram, count in pred_ngrams.items():
                clipped_totals[n - 1] += min(count, ref_ngrams.get(ngram, 0))

    precisions = []
    for clipped, total in zip(clipped_totals, prediction_totals):
        precisions.append((clipped + 1.0) / (total + 1.0))

    if prediction_length == 0:
        return 0.0
    brevity_penalty = 1.0 if prediction_length > reference_length else math.exp(1.0 - (reference_length / prediction_length))
    return brevity_penalty * math.exp(sum(math.log(precision) for precision in precisions) / max_n)


def get_teacher_forcing_ratio(config: ExperimentConfig, epoch: int) -> float:
    if not config.scheduled_sampling:
        return config.teacher_forcing_ratio

    if config.scheduled_sampling_strategy == "linear":
        progress = min(max((epoch - 1) / max(config.scheduled_sampling_decay_epochs, 1), 0.0), 1.0)
        ratio = config.teacher_forcing_ratio - progress * (config.teacher_forcing_ratio - config.scheduled_sampling_min_ratio)
        return max(config.scheduled_sampling_min_ratio, ratio)

    step = float(epoch)
    k = max(config.scheduled_sampling_inverse_sigmoid_k, 1e-6)
    ratio = k / (k + math.exp(step / k))
    ratio = min(ratio, config.teacher_forcing_ratio)
    return max(config.scheduled_sampling_min_ratio, ratio)


def run_epoch(
    model: nn.Module,
    loader: Iterable[dict[str, object]],
    device: torch.device,
    teacher_forcing_ratio: float,
    optimizer: torch.optim.Optimizer | None = None,
):
    is_training = optimizer is not None
    model.train(is_training)

    total_loss = 0.0
    total_token_accuracy = 0.0
    total_exact_match = 0.0
    total_examples = 0

    for batch in loader:
        batch = move_batch_to_device(batch, device)
        source_tokens = batch["source_tokens"]
        source_lengths = batch["source_lengths"]
        target_tokens = batch["target_tokens"]
        target_expected = target_tokens[:, 1:]

        if is_training:
            optimizer.zero_grad()

        logits, predictions, _ = model(
            source_tokens=source_tokens,
            source_lengths=source_lengths,
            target_tokens=target_tokens,
            teacher_forcing_ratio=teacher_forcing_ratio if is_training else 0.0,
        )
        loss = sequence_cross_entropy(logits, target_expected)

        if is_training:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()

        batch_size = target_tokens.size(0)
        token_accuracy, exact_match = compute_sequence_metrics(predictions, target_expected)
        total_loss += loss.item() * batch_size
        total_token_accuracy += token_accuracy * batch_size
        total_exact_match += exact_match * batch_size
        total_examples += batch_size

    return (
        total_loss / max(total_examples, 1),
        total_token_accuracy / max(total_examples, 1),
        total_exact_match / max(total_examples, 1),
    )


@torch.no_grad()
def evaluate_loader(model, loader, device):
    return run_epoch(model, loader, device, teacher_forcing_ratio=0.0, optimizer=None)


@torch.no_grad()
def collect_translation_samples(
    model: nn.Module,
    loader,
    device: torch.device,
    input_vocab: LanguageVocabulary,
    output_vocab: LanguageVocabulary,
    limit: int = 16,
):
    model.eval()
    rows: list[dict[str, object]] = []
    attention_rows: list[dict[str, object]] = []
    for batch in loader:
        batch = move_batch_to_device(batch, device)
        logits, predictions, attentions = model(
            source_tokens=batch["source_tokens"],
            source_lengths=batch["source_lengths"],
            target_tokens=None,
            teacher_forcing_ratio=0.0,
        )
        del logits
        for sample_index in range(predictions.size(0)):
            prediction_ids = predictions[sample_index].detach().cpu().tolist()
            prediction_text = output_vocab.decode(prediction_ids)
            target_text = batch["target_texts"][sample_index]
            source_text = batch["source_texts"][sample_index]
            prediction_trimmed = trim_at_eos(prediction_ids)
            target_ids = trim_at_eos(batch["target_tokens"][sample_index, 1:].detach().cpu().tolist())
            rows.append(
                {
                    "source_text": source_text,
                    "target_text": target_text,
                    "prediction_text": prediction_text,
                    "exact_match": int(prediction_trimmed == target_ids),
                    "source_length": int(batch["source_lengths"][sample_index].item()),
                }
            )
            if attentions is not None:
                attention_rows.append(
                    {
                        "source_text": source_text,
                        "prediction_text": prediction_text,
                        "attention": attentions[sample_index].detach().cpu(),
                    }
                )
            if len(rows) >= limit:
                return rows, attention_rows
    return rows, attention_rows


@torch.no_grad()
def collect_full_test_outputs(
    model: nn.Module,
    loader,
    device: torch.device,
    output_vocab: LanguageVocabulary,
):
    model.eval()
    rows: list[dict[str, object]] = []
    predictions_text: list[str] = []
    references_text: list[str] = []

    for batch in loader:
        batch = move_batch_to_device(batch, device)
        logits, predictions, _ = model(
            source_tokens=batch["source_tokens"],
            source_lengths=batch["source_lengths"],
            target_tokens=None,
            teacher_forcing_ratio=0.0,
        )
        del logits
        for sample_index in range(predictions.size(0)):
            prediction_ids = predictions[sample_index].detach().cpu().tolist()
            prediction_text = output_vocab.decode(prediction_ids)
            target_text = str(batch["target_texts"][sample_index])
            source_text = str(batch["source_texts"][sample_index])
            source_length = int(batch["source_lengths"][sample_index].item())
            predictions_text.append(prediction_text)
            references_text.append(target_text)
            rows.append(
                {
                    "source_text": source_text,
                    "target_text": target_text,
                    "prediction_text": prediction_text,
                    "exact_match": int(prediction_text == target_text),
                    "source_length": source_length,
                    "target_length": len(target_text.split(" ")),
                }
            )
    return rows, predictions_text, references_text


def compute_length_bucket_metrics(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets = {
        "1-3": lambda length: 1 <= length <= 3,
        "4-6": lambda length: 4 <= length <= 6,
        "7-9": lambda length: 7 <= length <= 9,
    }
    bucket_rows: list[dict[str, object]] = []
    for bucket_name, belongs in buckets.items():
        subset = [row for row in rows if belongs(int(row["source_length"]))]
        if not subset:
            bucket_rows.append(
                {
                    "bucket": bucket_name,
                    "sample_count": 0,
                    "exact_match": 0.0,
                    "bleu": 0.0,
                    "avg_target_length": 0.0,
                }
            )
            continue
        predictions = [str(row["prediction_text"]) for row in subset]
        references = [str(row["target_text"]) for row in subset]
        bucket_rows.append(
            {
                "bucket": bucket_name,
                "sample_count": len(subset),
                "exact_match": sum(int(row["exact_match"]) for row in subset) / len(subset),
                "bleu": compute_bleu_score(predictions, references),
                "avg_target_length": sum(int(row["target_length"]) for row in subset) / len(subset),
            }
        )
    return bucket_rows


def run_training(
    model: nn.Module,
    dataloaders: TranslationDataBundle,
    config: ExperimentConfig,
    output_dir,
):
    optimizer = build_optimizer(model, config)
    history: list[dict[str, float | int]] = []
    best_val_acc = -1.0
    best_val_loss = float("inf")
    best_val_exact_match = -1.0
    best_epoch = 0
    best_state = None
    start_time = time.time()
    if config.device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(config.device)

    for epoch in range(1, config.epochs + 1):
        epoch_start = time.time()
        teacher_forcing_ratio = get_teacher_forcing_ratio(config, epoch)
        train_loss, train_acc, train_exact_match = run_epoch(
            model,
            dataloaders.train_loader,
            config.device,
            teacher_forcing_ratio=teacher_forcing_ratio,
            optimizer=optimizer,
        )
        val_loss, val_acc, val_exact_match = evaluate_loader(model, dataloaders.val_loader, config.device)
        epoch_time = time.time() - epoch_start
        elapsed_train_time = time.time() - start_time

        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "train_acc": train_acc,
                "train_exact_match": train_exact_match,
                "val_loss": val_loss,
                "val_acc": val_acc,
                "val_exact_match": val_exact_match,
                "train_val_acc_gap": train_acc - val_acc,
                "teacher_forcing_ratio": teacher_forcing_ratio,
                "epoch_time_sec": epoch_time,
                "elapsed_train_time_sec": elapsed_train_time,
            }
        )

        print(
            f"Epoch [{epoch}/{config.epochs}] "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.2%} train_exact={train_exact_match:.2%} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.2%} val_exact={val_exact_match:.2%}"
            f" tf_ratio={teacher_forcing_ratio:.3f}"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_val_loss = val_loss
            best_val_exact_match = val_exact_match
            best_epoch = epoch
            best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
            torch.save(best_state, output_dir / "best_model.pth")

    if best_state is None:
        raise RuntimeError("Training did not produce a checkpoint.")

    model.load_state_dict(best_state)
    test_loss, test_acc, test_exact_match = evaluate_loader(model, dataloaders.test_loader, config.device)
    inference_metrics = measure_inference_time(model, dataloaders.test_loader, config.device)
    param_count, trainable_param_count = count_parameters(model)

    test_samples, attention_rows = collect_translation_samples(
        model,
        dataloaders.test_loader,
        config.device,
        dataloaders.input_vocab,
        dataloaders.output_vocab,
        limit=16,
    )
    all_test_rows, all_predictions, all_references = collect_full_test_outputs(
        model,
        dataloaders.test_loader,
        config.device,
        dataloaders.output_vocab,
    )
    length_bucket_metrics = compute_length_bucket_metrics(all_test_rows)
    test_bleu = compute_bleu_score(all_predictions, all_references)

    total_time = time.time() - start_time
    final_metrics = history[-1]
    peak_memory_mb = (
        torch.cuda.max_memory_allocated(config.device) / (1024 ** 2) if config.device.type == "cuda" else 0.0
    )
    avg_source_length = sum(len(source.split(" ")) for source, _ in dataloaders.raw_pairs) / max(
        len(dataloaders.raw_pairs), 1
    )
    avg_target_length = sum(len(target.split(" ")) for _, target in dataloaders.raw_pairs) / max(
        len(dataloaders.raw_pairs), 1
    )
    summary = {
        "best_val_acc": best_val_acc,
        "best_val_loss": best_val_loss,
        "best_val_exact_match": best_val_exact_match,
        "best_epoch": best_epoch,
        "final_train_loss": final_metrics["train_loss"],
        "final_train_acc": final_metrics["train_acc"],
        "final_train_exact_match": final_metrics["train_exact_match"],
        "final_val_loss": final_metrics["val_loss"],
        "final_val_acc": final_metrics["val_acc"],
        "final_val_exact_match": final_metrics["val_exact_match"],
        "final_train_val_acc_gap": final_metrics["train_val_acc_gap"],
        "test_loss": test_loss,
        "test_acc": test_acc,
        "test_exact_match": test_exact_match,
        "test_bleu": test_bleu,
        "total_train_time_sec": total_time,
        "avg_epoch_time_sec": total_time / max(config.epochs, 1),
        "param_count": param_count,
        "trainable_param_count": trainable_param_count,
        "peak_memory_mb": peak_memory_mb,
        "avg_source_length": avg_source_length,
        "avg_target_length": avg_target_length,
        "flops_per_sample": estimate_flops_per_sample(config.model, config.hidden_size, avg_source_length, avg_target_length),
    }
    summary.update(inference_metrics)

    save_epoch_metrics(history, output_dir / "epoch_metrics.csv")
    save_summary_metrics(summary, output_dir / "summary_metrics.csv")
    save_translation_samples(test_samples, output_dir / "sample_translations.csv")
    save_rows(all_test_rows, output_dir / "all_test_translations.csv")
    save_rows(length_bucket_metrics, output_dir / "length_bucket_metrics.csv")
    save_curves(history, output_dir / "training_curves.png")

    if attention_rows:
        attention_dir = output_dir / "attention_examples"
        ensure_dir(attention_dir)
        manifest_rows: list[dict[str, str]] = []
        for index, row in enumerate(attention_rows[:5], start=1):
            image_path = attention_dir / f"attention_{index:02d}.png"
            save_attention_heatmap(
                attention=row["attention"],
                source_text=str(row["source_text"]),
                prediction_text=str(row["prediction_text"]),
                path=image_path,
            )
            manifest_rows.append(
                {
                    "index": index,
                    "source_text": str(row["source_text"]),
                    "prediction_text": str(row["prediction_text"]),
                    "image_path": str(image_path),
                }
            )
        save_attention_rows(manifest_rows, output_dir / "attention_examples.csv")

    return summary
