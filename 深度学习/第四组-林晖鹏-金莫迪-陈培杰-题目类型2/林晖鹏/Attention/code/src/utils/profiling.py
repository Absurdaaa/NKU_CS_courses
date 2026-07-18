"""Profiling helpers for translation experiments."""

from __future__ import annotations

import time

import torch


def count_parameters(model) -> tuple[int, int]:
    total = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    return total, trainable


def estimate_flops_per_sample(model_name: str, hidden_size: int, avg_source_length: float, avg_target_length: float) -> float:
    source_steps = max(avg_source_length + 2.0, 1.0)
    target_steps = max(avg_target_length + 2.0, 1.0)
    encoder_flops = 6.0 * hidden_size * hidden_size * source_steps
    decoder_flops = 6.0 * hidden_size * hidden_size * target_steps
    attention_flops = hidden_size * source_steps * target_steps if model_name == "seq2seq_attn" else 0.0
    return encoder_flops + decoder_flops + attention_flops


def measure_inference_time(model, loader, device: torch.device, warmup_steps: int = 1) -> dict[str, float]:
    model.eval()
    batches = []
    for batch in loader:
        batches.append(batch)
        if len(batches) >= warmup_steps + 1:
            break
    if not batches:
        return {
            "test_inference_time_sec": 0.0,
            "inference_time_per_batch_sec": 0.0,
            "inference_time_per_sample_ms": 0.0,
        }

    def move(batch):
        return batch["source_tokens"].to(device), batch["source_lengths"].to(device)

    with torch.no_grad():
        for batch in batches[:warmup_steps]:
            source_tokens, source_lengths = move(batch)
            _ = model(source_tokens=source_tokens, source_lengths=source_lengths, target_tokens=None, teacher_forcing_ratio=0.0)
        if device.type == "cuda":
            torch.cuda.synchronize(device)

        start = time.perf_counter()
        total_samples = 0
        measured_batches = 0
        for batch in loader:
            source_tokens, source_lengths = move(batch)
            _ = model(source_tokens=source_tokens, source_lengths=source_lengths, target_tokens=None, teacher_forcing_ratio=0.0)
            total_samples += batch["source_tokens"].size(0)
            measured_batches += 1
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        elapsed = time.perf_counter() - start

    return {
        "test_inference_time_sec": elapsed,
        "inference_time_per_batch_sec": elapsed / max(measured_batches, 1),
        "inference_time_per_sample_ms": elapsed * 1000.0 / max(total_samples, 1),
    }
