"""Evaluation loop helpers."""

import torch
import torch.nn.functional as F

from engine.trainer import resolve_prediction_tensor
from utils.metrics import compute_e_measure, compute_f_measure, compute_iou, compute_mae, compute_max_f_measure, compute_pixel_accuracy, compute_s_measure


def _metric_bundle(probs, masks, prefix=""):
    mae = compute_mae(probs, masks)
    f_measure = compute_f_measure(probs, masks)
    max_f_measure, max_f_threshold = compute_max_f_measure(probs, masks)
    s_measure = compute_s_measure(probs, masks)
    e_measure = compute_e_measure(probs, masks)
    pixel_acc = compute_pixel_accuracy(probs, masks)
    iou = compute_iou(probs, masks)
    return {
        f"{prefix}mae": mae,
        f"{prefix}f_measure": f_measure,
        f"{prefix}max_f_measure": max_f_measure,
        f"{prefix}max_f_threshold": max_f_threshold,
        f"{prefix}s_measure": s_measure,
        f"{prefix}e_measure": e_measure,
        f"{prefix}pixel_acc": pixel_acc,
        f"{prefix}iou": iou,
    }


def _patch_metric_bundle(coarse_probs, final_probs, masks, boxes, delta_logits, prefix="patch_"):
    refined_mae_sum = 0.0
    coarse_mae_sum = 0.0
    refined_iou_sum = 0.0
    coarse_iou_sum = 0.0
    patch_count = 0

    for batch_index in range(boxes.shape[0]):
        for patch_index in range(boxes.shape[1]):
            x1, y1, x2, y2 = boxes[batch_index, patch_index].tolist()
            coarse_patch = coarse_probs[batch_index : batch_index + 1, :, y1:y2, x1:x2]
            final_patch = final_probs[batch_index : batch_index + 1, :, y1:y2, x1:x2]
            mask_patch = masks[batch_index : batch_index + 1, :, y1:y2, x1:x2]
            coarse_mae_sum += compute_mae(coarse_patch, mask_patch)
            refined_mae_sum += compute_mae(final_patch, mask_patch)
            coarse_iou_sum += compute_iou(coarse_patch, mask_patch)
            refined_iou_sum += compute_iou(final_patch, mask_patch)
            patch_count += 1

    if patch_count == 0:
        return {}

    coarse_mae = coarse_mae_sum / patch_count
    refined_mae = refined_mae_sum / patch_count
    coarse_iou = coarse_iou_sum / patch_count
    refined_iou = refined_iou_sum / patch_count

    return {
        f"{prefix}coarse_mae": coarse_mae,
        f"{prefix}refined_mae": refined_mae,
        f"{prefix}delta_mae": refined_mae - coarse_mae,
        f"{prefix}coarse_iou": coarse_iou,
        f"{prefix}refined_iou": refined_iou,
        f"{prefix}delta_iou": refined_iou - coarse_iou,
        f"{prefix}delta_abs_mean": delta_logits.abs().mean().item(),
        f"{prefix}delta_abs_max": delta_logits.abs().amax().item(),
    }


def _tta_probs(model, images, scales=(0.75, 1.0, 1.25)):
    """Test-time augmentation: average sigmoid maps over scales x h-flip.

    Each view is run through the model, the resulting saliency probability is
    de-augmented (flip back / resize back to the original resolution) and the
    views are averaged. Inference-only; the model is untouched.
    """
    height, width = images.shape[-2:]
    probs_sum = None
    count = 0
    for scale in scales:
        if scale == 1.0:
            scaled = images
        else:
            new_h = max(32, int(round(height * scale / 32)) * 32)
            new_w = max(32, int(round(width * scale / 32)) * 32)
            scaled = F.interpolate(images, size=(new_h, new_w), mode="bilinear", align_corners=False)
        for flip in (False, True):
            view = torch.flip(scaled, dims=[-1]) if flip else scaled
            prob = torch.sigmoid(resolve_prediction_tensor(model(view)))
            if flip:
                prob = torch.flip(prob, dims=[-1])
            if prob.shape[-2:] != (height, width):
                prob = F.interpolate(prob, size=(height, width), mode="bilinear", align_corners=False)
            probs_sum = prob if probs_sum is None else probs_sum + prob
            count += 1
    return probs_sum / count


@torch.no_grad()
def evaluate(model, loader, device="cpu", tta=False):
    model.to(device)
    model.eval()

    totals = {}
    total_items = 0

    for images, masks, _names in loader:
        images = images.to(device)
        masks = masks.to(device)

        if tta:
            probs = _tta_probs(model, images)
            metric_values = _metric_bundle(probs, masks)
            batch_size = images.size(0)
            for key, value in metric_values.items():
                totals[key] = totals.get(key, 0.0) + value * batch_size
            total_items += batch_size
            continue

        outputs = model(images)
        probs = torch.sigmoid(resolve_prediction_tensor(outputs))
        metric_values = _metric_bundle(probs, masks)

        if isinstance(outputs, dict) and "coarse" in outputs:
            coarse_probs = torch.sigmoid(outputs["coarse"])
            metric_values.update(_metric_bundle(coarse_probs, masks, prefix="coarse_"))
            if "boxes" in outputs and "delta" in outputs:
                metric_values.update(_patch_metric_bundle(coarse_probs, probs, masks, outputs["boxes"], outputs["delta"]))

        batch_size = images.size(0)
        for key, value in metric_values.items():
            totals[key] = totals.get(key, 0.0) + value * batch_size
        total_items += batch_size

    metrics = {key: value / max(total_items, 1) for key, value in totals.items()}
    if "coarse_mae" in metrics:
        metrics["delta_mae"] = metrics["mae"] - metrics["coarse_mae"]
        metrics["delta_max_f"] = metrics["max_f_measure"] - metrics["coarse_max_f_measure"]
        metrics["delta_iou"] = metrics["iou"] - metrics["coarse_iou"]
    return metrics
