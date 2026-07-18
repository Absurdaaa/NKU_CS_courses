"""Metrics for salient object detection."""

import torch


def _centroid(mask_2d):
    rows, cols = mask_2d.shape
    total = mask_2d.sum()
    if total <= 1e-6:
        return rows // 2, cols // 2
    ys = torch.arange(rows, device=mask_2d.device, dtype=mask_2d.dtype).view(rows, 1)
    xs = torch.arange(cols, device=mask_2d.device, dtype=mask_2d.dtype).view(1, cols)
    cy = torch.round((mask_2d * ys).sum() / total).long().item()
    cx = torch.round((mask_2d * xs).sum() / total).long().item()
    cy = max(0, min(cy, rows - 1))
    cx = max(0, min(cx, cols - 1))
    return cy, cx


def _ssim(pred, target):
    if pred.numel() == 0:
        return pred.new_tensor(0.0)
    pred_mean = pred.mean()
    target_mean = target.mean()
    pred_var = ((pred - pred_mean) ** 2).mean()
    target_var = ((target - target_mean) ** 2).mean()
    covariance = ((pred - pred_mean) * (target - target_mean)).mean()
    alpha = 4 * pred_mean * target_mean * covariance
    beta = (pred_mean.pow(2) + target_mean.pow(2)) * (pred_var + target_var)
    if alpha != 0:
        return alpha / (beta + 1e-6)
    if alpha == 0 and beta == 0:
        return pred.new_tensor(1.0)
    return pred.new_tensor(0.0)


def _object_score(pred, target):
    if pred.numel() == 0:
        return pred.new_tensor(0.0)
    mean_pred = pred.mean()
    std_pred = pred.std(unbiased=False)
    return 2 * mean_pred / (mean_pred.pow(2) + 1 + std_pred + 1e-6)


def compute_mae(pred, target):
    return torch.abs(pred - target).mean().item()


def compute_f_measure(pred, target, threshold=0.5, beta2=0.3, target_threshold=0.5):
    pred_bin = (pred >= threshold).float()
    target_bin = (target >= target_threshold).float()

    pred_flat = pred_bin.view(pred_bin.size(0), -1)
    target_flat = target_bin.view(target_bin.size(0), -1)
    tp = (pred_flat * target_flat).sum(dim=1)
    pred_pos = pred_flat.sum(dim=1)
    target_pos = target_flat.sum(dim=1)

    precision = torch.where(pred_pos > 0, tp / pred_pos.clamp_min(1e-6), torch.zeros_like(tp))
    recall = torch.where(target_pos > 0, tp / target_pos.clamp_min(1e-6), torch.zeros_like(tp))
    denom = beta2 * precision + recall
    f_measure = torch.where(
        denom > 0,
        (1 + beta2) * precision * recall / denom.clamp_min(1e-6),
        torch.zeros_like(denom),
    )
    return f_measure.mean().item()


def compute_max_f_measure(pred, target, beta2=0.3, num_thresholds=255):
    if num_thresholds < 2:
        raise ValueError("num_thresholds must be at least 2.")

    thresholds = torch.linspace(0.0, 1.0, steps=num_thresholds, device=pred.device, dtype=pred.dtype)
    best_f = -1.0
    best_threshold = 0.5
    for threshold in thresholds:
        threshold_value = threshold.item()
        current_f = compute_f_measure(pred, target, threshold=threshold_value, beta2=beta2)
        if current_f > best_f or (abs(current_f - best_f) <= 1e-8 and threshold_value > best_threshold):
            best_f = current_f
            best_threshold = threshold_value
    return best_f, best_threshold


def compute_pixel_accuracy(pred, target, threshold=0.5, target_threshold=0.5):
    pred_bin = (pred >= threshold).float()
    target_bin = (target >= target_threshold).float()
    return (pred_bin == target_bin).float().mean().item()


def compute_iou(pred, target, threshold=0.5, eps=1e-6, target_threshold=0.5):
    pred_bin = (pred >= threshold).float()
    target_bin = (target >= target_threshold).float()
    pred_flat = pred_bin.view(pred_bin.size(0), -1)
    target_flat = target_bin.view(target_bin.size(0), -1)
    inter = (pred_flat * target_flat).sum(dim=1)
    union = (pred_flat + target_flat - pred_flat * target_flat).sum(dim=1)
    return (inter / (union + eps)).mean().item()


def compute_s_measure(pred, target, alpha=0.5, eps=1e-6):
    pred = pred.clamp(0, 1)
    target = (target >= 0.5).float()
    scores = []
    for sample_pred, sample_target in zip(pred, target):
        sample_pred = sample_pred.squeeze(0)
        sample_target = sample_target.squeeze(0)
        gt_mean = sample_target.mean()
        if gt_mean <= eps:
            scores.append(1 - sample_pred.mean())
            continue
        if gt_mean >= 1 - eps:
            scores.append(sample_pred.mean())
            continue

        fg_score = _object_score(sample_pred[sample_target == 1], sample_target[sample_target == 1])
        bg_score = _object_score(1 - sample_pred[sample_target == 0], 1 - sample_target[sample_target == 0])
        object_score = gt_mean * fg_score + (1 - gt_mean) * bg_score

        cy, cx = _centroid(sample_target)
        h, w = sample_target.shape
        lt_pred = sample_pred[:cy, :cx]
        rt_pred = sample_pred[:cy, cx:]
        lb_pred = sample_pred[cy:, :cx]
        rb_pred = sample_pred[cy:, cx:]
        lt_gt = sample_target[:cy, :cx]
        rt_gt = sample_target[:cy, cx:]
        lb_gt = sample_target[cy:, :cx]
        rb_gt = sample_target[cy:, cx:]

        area = float(h * w)
        weights = [
            (cy * cx) / area,
            (cy * (w - cx)) / area,
            ((h - cy) * cx) / area,
            ((h - cy) * (w - cx)) / area,
        ]
        region_score = (
            weights[0] * _ssim(lt_pred, lt_gt)
            + weights[1] * _ssim(rt_pred, rt_gt)
            + weights[2] * _ssim(lb_pred, lb_gt)
            + weights[3] * _ssim(rb_pred, rb_gt)
        )
        score = alpha * object_score + (1 - alpha) * region_score
        scores.append(score.clamp(0, 1))
    return torch.stack([score if isinstance(score, torch.Tensor) else pred.new_tensor(score) for score in scores]).mean().item()


def compute_e_measure(pred, target, eps=1e-6):
    pred = pred.clamp(0, 1)
    target = (target >= 0.5).float()
    scores = []
    for sample_pred, sample_target in zip(pred, target):
        sample_pred = sample_pred.squeeze(0)
        sample_target = sample_target.squeeze(0)
        threshold = min(1.0, max(0.0, 2 * sample_pred.mean().item()))
        pred_bin = (sample_pred >= threshold).float()
        fm = pred_bin - pred_bin.mean()
        gm = sample_target - sample_target.mean()
        align_matrix = 2 * gm * fm / (gm.pow(2) + fm.pow(2) + eps)
        enhanced = ((align_matrix + 1) ** 2) / 4
        scores.append(enhanced.mean())
    return torch.stack(scores).mean().item()
