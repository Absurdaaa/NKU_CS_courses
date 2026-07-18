#!/usr/bin/env python3
"""Generate Grad-CAM comparison figures for the lab report."""

from __future__ import annotations

from pathlib import Path
import sys

CODE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CODE_ROOT.parent
sys.path.insert(0, str(CODE_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
from torchvision.datasets import CIFAR10
from torchvision.transforms import Compose, Normalize, ToTensor

from src.constants import CLASSES
from src.models import build_model
from src.utils.runtime import setup_matplotlib, set_seed

setup_matplotlib(PROJECT_ROOT)

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
REPORT_FIG_DIR = PROJECT_ROOT / "实验模板" / "fig" / "generated"
MODELS = [
    "simple_cnn",
    "resnet20",
    "densenet_bc_100",
    "mobilenet_v1",
    "res2net29_8c64w",
]
DISPLAY_NAMES = {
    "simple_cnn": "CNN",
    "resnet20": "ResNet20",
    "densenet_bc_100": "DenseNet-BC-100",
    "mobilenet_v1": "MobileNetV1",
    "res2net29_8c64w": "Res2Net",
}
MEAN = torch.tensor([0.5, 0.5, 0.5]).view(3, 1, 1)
STD = torch.tensor([0.5, 0.5, 0.5]).view(3, 1, 1)


class GradCAM:
    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module) -> None:
        self.model = model
        self.target_layer = target_layer
        self.activations: torch.Tensor | None = None
        self.gradients: torch.Tensor | None = None
        self.forward_handle = target_layer.register_forward_hook(self._save_activation)
        self.backward_handle = target_layer.register_full_backward_hook(self._save_gradient)

    def _save_activation(self, _module, _inputs, output) -> None:
        self.activations = output.detach()

    def _save_gradient(self, _module, _grad_input, grad_output) -> None:
        self.gradients = grad_output[0].detach()

    def __call__(self, image: torch.Tensor, class_idx: int) -> np.ndarray:
        self.model.zero_grad(set_to_none=True)
        logits = self.model(image)
        score = logits[:, class_idx].sum()
        score.backward(retain_graph=False)

        if self.activations is None or self.gradients is None:
            raise RuntimeError("Grad-CAM hooks did not capture activations/gradients.")

        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = (weights * self.activations).sum(dim=1, keepdim=True)
        cam = F.relu(cam)
        cam = F.interpolate(cam, size=image.shape[-2:], mode="bilinear", align_corners=False)
        cam = cam.squeeze().cpu().numpy()
        cam_min, cam_max = float(cam.min()), float(cam.max())
        if cam_max > cam_min:
            cam = (cam - cam_min) / (cam_max - cam_min)
        else:
            cam = np.zeros_like(cam)
        return cam

    def close(self) -> None:
        self.forward_handle.remove()
        self.backward_handle.remove()


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def get_target_layer(model_name: str, model: torch.nn.Module) -> torch.nn.Module:
    if model_name == "simple_cnn":
        return model.features[6]
    if model_name == "resnet20":
        return model.layer3[-1].conv2
    if model_name == "densenet_bc_100":
        return model.blocks[-1].layers[-1].conv2
    if model_name == "mobilenet_v1":
        return model.features[-1].pointwise[0]
    if model_name == "res2net29_8c64w":
        return model.layer3[-1].conv3
    raise ValueError(f"Unsupported model for Grad-CAM: {model_name}")


def load_model(model_name: str, device: torch.device) -> torch.nn.Module:
    best_info = {}
    with (OUTPUTS_DIR / model_name / f"{model_name}_sgd_best_lr.txt").open("r", encoding="utf-8") as file:
        for line in file:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                best_info[key] = value

    checkpoint_path = OUTPUTS_DIR / model_name / best_info["run_name"] / "best_model.pth"
    model = build_model(model_name).to(device)
    state = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state)
    for module in model.modules():
        if isinstance(module, torch.nn.ReLU):
            module.inplace = False
    model.eval()
    return model


def build_dataset() -> CIFAR10:
    transform = Compose(
        [
            ToTensor(),
            Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )
    return CIFAR10(
        root=str(PROJECT_ROOT / "data"),
        train=False,
        download=False,
        transform=transform,
    )


def denormalize(image: torch.Tensor) -> np.ndarray:
    image = image.detach().cpu() * STD + MEAN
    image = image.clamp(0.0, 1.0)
    return image.permute(1, 2, 0).numpy()


def choose_examples(
    dataset: CIFAR10,
    models: dict[str, torch.nn.Module],
    device: torch.device,
    limit: int = 300,
    count: int = 2,
) -> list[int]:
    selected: list[int] = []
    seen_labels: set[int] = set()
    for idx in range(min(limit, len(dataset))):
        image, label = dataset[idx]
        batch = image.unsqueeze(0).to(device)
        ok = True
        for model in models.values():
            with torch.no_grad():
                pred = int(model(batch).argmax(dim=1).item())
            if pred != label:
                ok = False
                break
        if ok and label not in seen_labels:
            selected.append(idx)
            seen_labels.add(label)
        if len(selected) >= count:
            break
    if len(selected) < count:
        raise RuntimeError("Could not find enough consensus-correct test samples for Grad-CAM.")
    return selected


def overlay_heatmap(image: np.ndarray, cam: np.ndarray) -> np.ndarray:
    cmap = plt.get_cmap("jet")
    heatmap = cmap(cam)[..., :3]
    overlay = 0.45 * image + 0.55 * heatmap
    return np.clip(overlay, 0.0, 1.0)


def generate_figure() -> Path:
    set_seed(42)
    device = get_device()
    dataset = build_dataset()
    REPORT_FIG_DIR.mkdir(parents=True, exist_ok=True)

    models = {name: load_model(name, device) for name in MODELS}
    cams = {name: GradCAM(models[name], get_target_layer(name, models[name])) for name in MODELS}

    indices = choose_examples(dataset, models, device)
    fig, axes = plt.subplots(len(indices), len(MODELS) + 1, figsize=(15, 5.2))
    if len(indices) == 1:
        axes = np.expand_dims(axes, axis=0)

    for row, idx in enumerate(indices):
        image, label = dataset[idx]
        image_batch = image.unsqueeze(0).to(device)
        rgb = denormalize(image)

        axes[row, 0].imshow(rgb)
        axes[row, 0].set_title(f"Original\nGT={CLASSES[label]}", fontsize=10)
        axes[row, 0].axis("off")

        for col, model_name in enumerate(MODELS, start=1):
            model = models[model_name]
            with torch.no_grad():
                pred = int(model(image_batch).argmax(dim=1).item())
            cam = cams[model_name](image_batch, pred)
            overlay = overlay_heatmap(rgb, cam)
            axes[row, col].imshow(overlay)
            axes[row, col].set_title(
                f"{DISPLAY_NAMES[model_name]}\nPred={CLASSES[pred]}",
                fontsize=10,
            )
            axes[row, col].axis("off")

    fig.suptitle("Grad-CAM comparison on CIFAR-10 test images", fontsize=14, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out_path = REPORT_FIG_DIR / "gradcam_comparison.png"
    fig.savefig(out_path, dpi=240, bbox_inches="tight")
    plt.close(fig)

    for cam in cams.values():
        cam.close()
    return out_path


def main() -> None:
    out_path = generate_figure()
    print(out_path)


if __name__ == "__main__":
    main()
