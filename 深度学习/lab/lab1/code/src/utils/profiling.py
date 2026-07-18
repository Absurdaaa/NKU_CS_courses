"""Model profiling and timing helpers."""

from __future__ import annotations

import time
from typing import Dict, Tuple

import torch
import torch.nn as nn


def sync_device(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def count_parameters(model: nn.Module) -> Tuple[int, int]:
    total_params = sum(param.numel() for param in model.parameters())
    trainable_params = sum(
        param.numel() for param in model.parameters() if param.requires_grad
    )
    return total_params, trainable_params


def _conv2d_flops(module: nn.Conv2d, output: torch.Tensor) -> int:
    batch_size, out_channels, out_h, out_w = output.shape
    kernel_h, kernel_w = module.kernel_size
    in_channels = module.in_channels
    groups = module.groups
    filters_per_channel = out_channels // groups
    conv_per_position = kernel_h * kernel_w * in_channels * filters_per_channel
    active_elements = batch_size * out_h * out_w
    return int(active_elements * conv_per_position)


def _linear_flops(module: nn.Linear, output: torch.Tensor) -> int:
    batch_size = output.shape[0] if output.ndim > 1 else 1
    return int(batch_size * module.in_features * module.out_features)


def _batchnorm2d_flops(module: nn.BatchNorm2d, output: torch.Tensor) -> int:
    return int(output.numel() * 2)


def _relu_flops(module: nn.Module, output: torch.Tensor) -> int:
    return int(output.numel())


def _pool_flops(module: nn.Module, output: torch.Tensor) -> int:
    return int(output.numel())


def estimate_flops(
    model: nn.Module,
    device: torch.device,
    input_shape: Tuple[int, int, int, int] = (1, 3, 32, 32),
) -> int:
    flops = 0
    hooks = []
    was_training = model.training

    def hook_fn(module: nn.Module, inputs: Tuple[torch.Tensor, ...], output: torch.Tensor) -> None:
        nonlocal flops
        if isinstance(module, nn.Conv2d):
            flops += _conv2d_flops(module, output)
        elif isinstance(module, nn.Linear):
            flops += _linear_flops(module, output)
        elif isinstance(module, nn.BatchNorm2d):
            flops += _batchnorm2d_flops(module, output)
        elif isinstance(module, (nn.ReLU, nn.ReLU6)):
            flops += _relu_flops(module, output)
        elif isinstance(module, (nn.MaxPool2d, nn.AvgPool2d, nn.AdaptiveAvgPool2d)):
            flops += _pool_flops(module, output)

    for module in model.modules():
        if module is model:
            continue
        if isinstance(
            module,
            (
                nn.Conv2d,
                nn.Linear,
                nn.BatchNorm2d,
                nn.ReLU,
                nn.ReLU6,
                nn.MaxPool2d,
                nn.AvgPool2d,
                nn.AdaptiveAvgPool2d,
            ),
        ):
            hooks.append(module.register_forward_hook(hook_fn))

    model.eval()
    with torch.no_grad():
        sample = torch.randn(*input_shape, device=device)
        _ = model(sample)

    for hook in hooks:
        hook.remove()
    model.train(was_training)
    return flops


def measure_inference_time(
    model: nn.Module,
    device: torch.device,
    sample_inputs: torch.Tensor,
    warmup: int = 5,
    repeat: int = 20,
) -> Dict[str, float]:
    was_training = model.training
    model.eval()
    sample_inputs = sample_inputs.to(device)

    with torch.no_grad():
        for _ in range(warmup):
            _ = model(sample_inputs)
        sync_device(device)

        start = time.perf_counter()
        for _ in range(repeat):
            _ = model(sample_inputs)
        sync_device(device)
        total_time = time.perf_counter() - start

    model.train(was_training)

    total_samples = repeat * sample_inputs.size(0)
    return {
        "inference_total_time_sec": total_time,
        "inference_time_per_batch_sec": total_time / repeat,
        "inference_time_per_image_ms": total_time / total_samples * 1000.0,
    }
