from __future__ import annotations

import torch.nn as nn
from torchvision import models

from .densenet import densenet_bc_100
from .mobilenet import mobilenet_v1
from .res2net import res2net29_8c64w
from .resnet import resnet20
from .simple_cnn import SimpleCNN


AVAILABLE_MODELS = (
    "simple_cnn",
    "resnet20",
    "res2net29_8c64w",
    "densenet_bc_100",
    "mobilenet_v1",
    "vgg11_bn",
)


def build_model(model_name: str, num_classes: int = 10) -> nn.Module:
    if model_name == "simple_cnn":
        return SimpleCNN(num_classes=num_classes)
    if model_name == "resnet20":
        return resnet20(num_classes=num_classes)
    if model_name == "res2net29_8c64w":
        return res2net29_8c64w(num_classes=num_classes)
    if model_name == "densenet_bc_100":
        return densenet_bc_100(num_classes=num_classes)
    if model_name == "mobilenet_v1":
        return mobilenet_v1(num_classes=num_classes)
    if model_name == "vgg11_bn":
        model = models.vgg11_bn(weights=None)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
        return model
    raise ValueError(f"Unsupported model: {model_name}")
