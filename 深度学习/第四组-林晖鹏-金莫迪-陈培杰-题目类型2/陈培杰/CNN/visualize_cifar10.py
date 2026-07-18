import os
import random
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms as T
import torchvision.datasets as datasets
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam import base_cam

from SimpleCNN import get_SimpleNet, get_CustomNet
from ResNet import get_ResNet1
from DenseNet import get_DenseNet
from MobileNet0 import get_MobileNet
from Res2Net import get_Res2Net


CIFAR10_MEAN = (0.4914, 0.4822, 0.4465)
CIFAR10_STD = (0.2023, 0.1994, 0.2010)
CIFAR10_LABELS = [
    "airplane",
    "automobile",
    "bird",
    "cat",
    "deer",
    "dog",
    "frog",
    "horse",
    "ship",
    "truck",
]


def _patch_gradcam_del():
    if not hasattr(base_cam, "BaseCAM"):
        return

    def safe_del(self):
        if hasattr(self, "activations_and_grads") and self.activations_and_grads is not None:
            try:
                self.activations_and_grads.release()
            except Exception:
                pass

    base_cam.BaseCAM.__del__ = safe_del


_patch_gradcam_del()


@dataclass
class ModelSpec:
    name: str
    builder: callable
    gradcam_target: nn.Module
    feature_target: nn.Module
    shallow_target: nn.Module


def get_test_loader(batch_size=128, data_dir="data"):
    transform = T.Compose([
        T.ToTensor(),
        T.Normalize(mean=CIFAR10_MEAN, std=CIFAR10_STD),
    ])
    test_dataset = datasets.CIFAR10(data_dir, train=False, transform=transform, download=True)
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    return test_dataset, test_loader


def denormalize(img_tensor):
    mean = torch.tensor(CIFAR10_MEAN, device=img_tensor.device).view(1, 3, 1, 1)
    std = torch.tensor(CIFAR10_STD, device=img_tensor.device).view(1, 3, 1, 1)
    return img_tensor * std + mean


def find_first_conv(module):
    for m in module.modules():
        if isinstance(m, nn.Conv2d):
            return m
    raise ValueError("No Conv2d layer found.")


def find_last_conv(module):
    last = None
    for m in module.modules():
        if isinstance(m, nn.Conv2d):
            last = m
    if last is None:
        raise ValueError("No Conv2d layer found.")
    return last


def find_last_linear(module):
    last = None
    for m in module.modules():
        if isinstance(m, nn.Linear):
            last = m
    if last is None:
        raise ValueError("No Linear layer found.")
    return last


def build_models(device, model_dir="model"):
    builders = {
        "SimpleNet": get_SimpleNet,
        "CustomNet": get_CustomNet,
        "ResNet": get_ResNet1,
        "DenseNet": get_DenseNet,
        "MobileNet": get_MobileNet,
        "Res2Net": get_Res2Net,
    }

    models = {}
    for name, builder in builders.items():
        model = builder().to(device)
        weight_path = os.path.join(model_dir, f"{name}.pth")
        if os.path.exists(weight_path):
            state = torch.load(weight_path, map_location=device)
            if isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]
            # Ignore thop bookkeeping keys like total_ops/total_params.
            state = {k: v for k, v in state.items() if "total_ops" not in k and "total_params" not in k}
            model.load_state_dict(state, strict=False)
        model.eval()
        models[name] = model
    return models


def build_model_specs(models):
    specs = {}
    for name, model in models.items():
        # EDIT TARGET LAYERS HERE if your model uses custom names, e.g. model.layer4 or model.conv1.
        gradcam_target = find_last_conv(model)
        feature_target = find_last_linear(model)
        shallow_target = find_first_conv(model)
        specs[name] = ModelSpec(
            name=name,
            builder=None,
            gradcam_target=gradcam_target,
            feature_target=feature_target,
            shallow_target=shallow_target,
        )
    return specs


def create_gradcam(model, target_layers, use_cuda):
    try:
        return GradCAM(model=model, target_layers=target_layers, use_cuda=use_cuda)
    except TypeError:
        return GradCAM(model=model, target_layers=target_layers)


def plot_grad_cam(models, model_specs, test_dataset, device, image_index=None, save_path=None):
    model_names = ["SimpleNet", "CustomNet", "ResNet", "DenseNet", "MobileNet", "Res2Net"]
    if image_index is None:
        image_index = random.randint(0, len(test_dataset) - 1)

    img_tensor, _ = test_dataset[image_index]
    img_batch = img_tensor.unsqueeze(0).to(device)

    img_vis = denormalize(img_batch).clamp(0, 1)
    img_vis = img_vis[0].permute(1, 2, 0).cpu().numpy()
    img_vis = np.clip(img_vis, 0, 1)

    fig, axes = plt.subplots(1, len(model_names) + 1, figsize=(3.5 * (len(model_names) + 1), 4))
    axes[0].imshow(img_vis)
    axes[0].set_title("Original")
    axes[0].axis("off")

    for i, name in enumerate(model_names, start=1):
        model = models[name]
        spec = model_specs[name]
        use_cuda = device.type == "cuda"

        # pytorch-grad-cam uses forward hooks on target_layers internally.
        with torch.no_grad():
            logits = model(img_batch)
            class_idx = int(logits.argmax(dim=1).item())

        cam = create_gradcam(model, [spec.gradcam_target], use_cuda)
        try:
            grayscale_cam = cam(input_tensor=img_batch, targets=[ClassifierOutputTarget(class_idx)])
        finally:
            if hasattr(cam, "activations_and_grads") and cam.activations_and_grads is not None:
                cam.activations_and_grads.release()
        cam_image = show_cam_on_image(img_vis, grayscale_cam[0], use_rgb=True)

        axes[i].imshow(cam_image)
        axes[i].set_title(name)
        axes[i].axis("off")

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=200)
        plt.close()
    else:
        plt.show()


def extract_features(model, feature_layer, data_loader, device, max_samples=1000):
    features = []
    labels = []
    count = 0

    def hook(module, inputs, output):
        feat = inputs[0].detach().cpu()
        features.append(feat)

    handle = feature_layer.register_forward_hook(hook)
    model.eval()
    with torch.no_grad():
        for x, y in data_loader:
            remaining = max_samples - count
            if remaining <= 0:
                break
            x = x[:remaining].to(device)
            y = y[:remaining]
            _ = model(x)
            labels.append(y)
            count += x.shape[0]

    handle.remove()

    features = torch.cat(features, dim=0).numpy()
    labels = torch.cat(labels, dim=0).numpy()
    return features, labels


def plot_tsne_clusters(models, model_specs, test_loader, device, save_path=None):
    model_names = ["SimpleNet", "CustomNet", "ResNet", "DenseNet", "MobileNet", "Res2Net"]
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for ax, name in zip(axes, model_names):
        model = models[name]
        spec = model_specs[name]
        features, labels = extract_features(model, spec.feature_target, test_loader, device, max_samples=1000)

        tsne = TSNE(n_components=2, random_state=42, init="pca", learning_rate="auto")
        z = tsne.fit_transform(features)

        colors = plt.cm.tab10.colors
        for cls in range(10):
            idx = labels == cls
            ax.scatter(z[idx, 0], z[idx, 1], s=8, color=colors[cls], label=CIFAR10_LABELS[cls], alpha=0.8)

        ax.set_title(name)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.legend(loc="best", fontsize=8, ncol=2, frameon=False)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=200)
        plt.close()
    else:
        plt.show()


def plot_shallow_feature_maps(models, model_specs, test_dataset, device, image_index=None, save_dir=None):
    model_names = ["SimpleNet", "CustomNet", "ResNet", "DenseNet", "MobileNet", "Res2Net"]
    if image_index is None:
        image_index = random.randint(0, len(test_dataset) - 1)

    img_tensor, _ = test_dataset[image_index]
    img_batch = img_tensor.unsqueeze(0).to(device)

    for name in model_names:
        model = models[name]
        spec = model_specs[name]
        feature_maps = {}

        def hook(module, inputs, output):
            feature_maps["value"] = output.detach().cpu()

        handle = spec.shallow_target.register_forward_hook(hook)
        _ = model(img_batch)
        handle.remove()

        fmap = feature_maps["value"][0]
        fig, axes = plt.subplots(4, 4, figsize=(6, 6))
        fig.suptitle(f"{name} shallow features")

        for i, ax in enumerate(axes.flatten()):
            if i < fmap.shape[0]:
                ax.imshow(fmap[i], cmap="gray")
            ax.axis("off")

        plt.tight_layout()
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            plt.savefig(os.path.join(save_dir, f"{name}_shallow_features.png"), dpi=200)
            plt.close()
        else:
            plt.show()


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_dataset, test_loader = get_test_loader(batch_size=128, data_dir=os.path.join(base_dir, "data"))

    models = build_models(device=device, model_dir=os.path.join(base_dir, "model"))
    model_specs = build_model_specs(models)

    plot_grad_cam(models, model_specs, test_dataset, device, save_path=os.path.join(base_dir, "gradcam_grid.png"))
    plot_tsne_clusters(models, model_specs, test_loader, device, save_path=os.path.join(base_dir, "tsne_clusters.png"))
    plot_shallow_feature_maps(models, model_specs, test_dataset, device, save_dir=os.path.join(base_dir, "shallow_features"))


if __name__ == "__main__":
    main()
