"""Profiling helpers for RNN/LSTM experiments."""

from __future__ import annotations

import time

import torch


def count_parameters(model) -> tuple[int, int]:
    total = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    return total, trainable


def estimate_flops_per_sample(model_name: str, input_size: int, hidden_size: int, output_size: int, avg_length: float) -> float:
    # RNN/LSTM 的 FLOPs 这里使用解析式近似估算，便于做相对比较，不是严格 profiler 数值
    sequence_length = max(avg_length, 1.0)
    if model_name == "rnn":
        recurrent_flops = 2.0 * (input_size + hidden_size) * hidden_size
        head_flops = 2.0 * hidden_size * output_size
        return sequence_length * recurrent_flops + head_flops
    if model_name == "lstm":
        gate_flops = 2.0 * 4.0 * ((input_size * hidden_size) + (hidden_size * hidden_size))
        head_flops = 2.0 * hidden_size * output_size
        return sequence_length * gate_flops + head_flops
    return 0.0


def measure_inference_time(model, loader, device: torch.device, warmup_steps: int = 2) -> dict[str, float]:
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
        return batch["sequences"].to(device), batch["lengths"].to(device)

    with torch.no_grad():
        for batch in batches[:warmup_steps]:
            sequences, lengths = move(batch)
            _ = model(sequences, lengths)
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        # 预热后再计时，减少首次调用带来的额外开销
        start = time.perf_counter()
        total_samples = 0
        measured_batches = 0
        for batch in loader:
            sequences, lengths = move(batch)
            _ = model(sequences, lengths)
            total_samples += batch["labels"].size(0)
            measured_batches += 1
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        elapsed = time.perf_counter() - start

    return {
        "test_inference_time_sec": elapsed,
        "inference_time_per_batch_sec": elapsed / max(measured_batches, 1),
        "inference_time_per_sample_ms": elapsed * 1000.0 / max(total_samples, 1),
    }
