"""I/O helpers."""

import csv
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw
import torch


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def save_checkpoint(state, path):
    path = Path(path)
    ensure_dir(path.parent)
    torch.save(state, path)


def load_checkpoint(path, map_location="cpu"):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")
    return torch.load(path, map_location=map_location)


def load_state_dict_compat(model, state_dict):
    state_dict = dict(state_dict)
    if "patch_refiner.out.weight" in state_dict and "patch_refiner.delta_head.weight" not in state_dict:
        state_dict["patch_refiner.delta_head.weight"] = state_dict.pop("patch_refiner.out.weight")
        state_dict["patch_refiner.delta_head.bias"] = state_dict.pop("patch_refiner.out.bias")
        gate_weight = model.patch_refiner.gate_head.weight.detach().clone().zero_()
        gate_bias = model.patch_refiner.gate_head.bias.detach().clone().zero_()
        state_dict["patch_refiner.gate_head.weight"] = gate_weight
        state_dict["patch_refiner.gate_head.bias"] = gate_bias
    model.load_state_dict(state_dict, strict=True)


def save_prediction(mask_tensor, path):
    path = Path(path)
    ensure_dir(path.parent)
    mask = (mask_tensor.clamp(0, 1) * 255).byte().cpu().squeeze().numpy()
    Image.fromarray(mask).save(path)


def save_json(data, path):
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_csv_row(path, row):
    path = Path(path)
    ensure_dir(path.parent)
    fieldnames = list(row.keys())
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def make_timestamp():
    return datetime.now().isoformat(timespec="seconds")


def _tensor_to_rgb_image(image_tensor):
    image = image_tensor.detach().clamp(0, 1).mul(255).byte().permute(1, 2, 0).cpu().numpy()
    return Image.fromarray(image)


def _tensor_to_gray_image(mask_tensor):
    mask = mask_tensor.detach().clamp(0, 1).mul(255).byte().squeeze().cpu().numpy()
    return Image.fromarray(mask, mode="L").convert("RGB")


def _tensor_to_signed_heatmap(tensor):
    tensor = tensor.detach().squeeze().cpu()
    max_abs = tensor.abs().amax().item()
    if max_abs < 1e-6:
        max_abs = 1.0
    normalized = (tensor / max_abs).clamp(-1, 1)

    positive = normalized.clamp(min=0)
    negative = (-normalized).clamp(min=0)
    neutral = 1 - normalized.abs()

    image = torch.stack(
        [
            positive,
            neutral * 0.95 + positive * 0.05,
            negative,
        ],
        dim=0,
    )
    image = image.clamp(0, 1).mul(255).byte().permute(1, 2, 0).numpy()
    return Image.fromarray(image)


def save_zoom_visualization(image_tensor, gt_tensor, uncertainty_tensor, coarse_prob, final_prob, delta_tensor, boxes, path):
    path = Path(path)
    ensure_dir(path.parent)

    original = _tensor_to_rgb_image(image_tensor)
    gt = _tensor_to_gray_image(gt_tensor)
    uncertainty = _tensor_to_gray_image(uncertainty_tensor)
    coarse = _tensor_to_gray_image(coarse_prob)
    final = _tensor_to_gray_image(final_prob)
    delta = _tensor_to_signed_heatmap(delta_tensor)
    refine_delta = _tensor_to_signed_heatmap(final_prob - coarse_prob)

    for canvas in (original, gt, uncertainty):
        draw = ImageDraw.Draw(canvas)
        for box in boxes:
            x1, y1, x2, y2 = [int(v) for v in box]
            draw.rectangle((x1, y1, x2, y2), outline=(255, 0, 0), width=2)

    width, height = original.size
    grid = Image.new("RGB", (width * 6, height), color=(0, 0, 0))
    grid.paste(original, (0, 0))
    grid.paste(gt, (width, 0))
    grid.paste(uncertainty, (width * 2, 0))
    grid.paste(coarse, (width * 3, 0))
    grid.paste(final, (width * 4, 0))
    grid.paste(refine_delta, (width * 5, 0))
    grid.save(path)

    patch_dir = path.parent / f"{path.stem}_patches"
    ensure_dir(patch_dir)
    for patch_index, box in enumerate(boxes):
        x1, y1, x2, y2 = [int(v) for v in box]
        rgb_patch = original.crop((x1, y1, x2, y2))
        gt_patch = gt.crop((x1, y1, x2, y2))
        unc_patch = uncertainty.crop((x1, y1, x2, y2))
        coarse_patch = coarse.crop((x1, y1, x2, y2))
        final_patch = final.crop((x1, y1, x2, y2))
        refine_delta_patch = refine_delta.crop((x1, y1, x2, y2))
        delta_patch = delta.crop((x1, y1, x2, y2))
        patch_canvas = Image.new("RGB", (rgb_patch.width * 7, rgb_patch.height), color=(0, 0, 0))
        patch_canvas.paste(rgb_patch, (0, 0))
        patch_canvas.paste(gt_patch, (rgb_patch.width, 0))
        patch_canvas.paste(unc_patch, (rgb_patch.width * 2, 0))
        patch_canvas.paste(coarse_patch, (rgb_patch.width * 3, 0))
        patch_canvas.paste(final_patch, (rgb_patch.width * 4, 0))
        patch_canvas.paste(refine_delta_patch, (rgb_patch.width * 5, 0))
        patch_canvas.paste(delta_patch, (rgb_patch.width * 6, 0))
        patch_canvas.save(patch_dir / f"patch_{patch_index:02d}.png")
