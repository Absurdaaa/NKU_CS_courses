"""Device and DataParallel helpers."""

import torch


def parse_gpu_ids(gpu_ids):
    values = []
    for item in gpu_ids.split(","):
        item = item.strip()
        if item:
            values.append(int(item))
    return values


def unwrap_model(model):
    return model.module if hasattr(model, "module") else model


def resolve_runtime_device(device, gpu_ids):
    if not str(device).startswith("cuda") or not torch.cuda.is_available():
        return device
    ids = parse_gpu_ids(gpu_ids)
    if ids:
        return f"cuda:{ids[0]}"
    return "cuda:0"


def maybe_wrap_data_parallel(model, device, gpu_ids):
    if not device.startswith("cuda") or not torch.cuda.is_available():
        return model, []
    ids = parse_gpu_ids(gpu_ids)
    if len(ids) <= 1:
        return model, ids
    return torch.nn.DataParallel(model, device_ids=ids), ids
