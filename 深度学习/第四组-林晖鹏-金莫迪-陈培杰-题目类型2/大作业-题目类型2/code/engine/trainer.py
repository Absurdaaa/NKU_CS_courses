"""Training loop helpers for structured model outputs."""

import torch


def resolve_model_outputs(outputs):
    if isinstance(outputs, dict):
        return outputs
    if isinstance(outputs, (tuple, list)):
        return {"pred": outputs[-1], "raw": list(outputs)}
    return {"pred": outputs}


def resolve_prediction_tensor(outputs):
    resolved = resolve_model_outputs(outputs)
    return resolved["pred"]


def train_one_epoch(model, loader, criterion, optimizer, device="cpu", grad_clip=None):
    model.to(device)
    model.train()

    total_loss = 0.0
    total_items = 0

    for images, masks, _names in loader:
        images = images.to(device)
        masks = masks.to(device)

        optimizer.zero_grad()
        outputs = resolve_model_outputs(model(images))
        if hasattr(model, "compute_loss"):
            loss = model.compute_loss(outputs, masks)
        else:
            loss = criterion(outputs["pred"], masks)
        loss.backward()
        if grad_clip is not None and grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=grad_clip)
        optimizer.step()

        batch_size = images.size(0)
        total_loss += loss.item() * batch_size
        total_items += batch_size

    return total_loss / max(total_items, 1)
