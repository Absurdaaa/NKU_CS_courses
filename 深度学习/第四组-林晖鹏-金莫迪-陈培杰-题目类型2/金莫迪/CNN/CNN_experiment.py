from __future__ import annotations

import csv
import copy
import random
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
import torchvision.transforms as T
from torch.utils.data import DataLoader
from torchvision.utils import save_image

try:
    from tqdm.auto import tqdm
except Exception:
    tqdm = None

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data"
OUT = ROOT / "CNN" / "results"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED = 2026


def loop(x, **kwargs):
    return tqdm(x, **kwargs) if tqdm is not None else x


def ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def confusion_matrix(y_true: list[int], y_pred: list[int], n_classes: int) -> list[list[int]]:
    mat = [[0] * n_classes for _ in range(n_classes)]
    for t, p in zip(y_true, y_pred):
        mat[t][p] += 1
    return mat


def save_confusion(path: Path, mat: list[list[int]], labels: list[str]) -> None:
    rows = []
    for i, row in enumerate(mat):
        item = {"label": labels[i]}
        item.update({labels[j]: v for j, v in enumerate(row)})
        rows.append(item)
    write_csv(path, rows)


class SimpleCNN(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1), nn.ReLU(True), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(True), nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(nn.Flatten(), nn.Linear(32 * 8 * 8, 128), nn.ReLU(True), nn.Linear(128, num_classes))

    def forward(self, x):
        return self.classifier(self.features(x))


class ResBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=1, bias=False), nn.BatchNorm2d(channels), nn.ReLU(True),
            nn.Conv2d(channels, channels, 3, padding=1, bias=False), nn.BatchNorm2d(channels),
        )

    def forward(self, x):
        return F.relu(x + self.net(x), inplace=True)


class MicroResNet(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv2d(3, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(True))
        self.layer1 = ResBlock(32)
        self.down = nn.Sequential(nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.BatchNorm2d(64), nn.ReLU(True))
        self.layer2 = ResBlock(64)
        self.head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(64, num_classes))

    def forward(self, x):
        return self.head(self.layer2(self.down(self.layer1(self.stem(x)))))


class Res2NetBlock(nn.Module):
    def __init__(self, channels, scale=4):
        super().__init__()
        self.scale = scale
        self.width = channels // scale
        self.conv1 = nn.Conv2d(channels, channels, 1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.convs = nn.ModuleList([nn.Conv2d(self.width, self.width, 3, padding=1, bias=False) for _ in range(scale - 1)])
        self.bns = nn.ModuleList([nn.BatchNorm2d(self.width) for _ in range(scale - 1)])
        self.conv3 = nn.Conv2d(channels, channels, 1, bias=False)
        self.bn3 = nn.BatchNorm2d(channels)

    def forward(self, x):
        residual = x
        chunks = torch.split(F.relu(self.bn1(self.conv1(x)), inplace=True), self.width, dim=1)
        outputs, running = [], None
        for i in range(self.scale - 1):
            running = chunks[i] if i == 0 else running + chunks[i]
            running = F.relu(self.bns[i](self.convs[i](running)), inplace=True)
            outputs.append(running)
        outputs.append(chunks[-1])
        return F.relu(self.bn3(self.conv3(torch.cat(outputs, dim=1))) + residual, inplace=True)


class MicroRes2Net(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv2d(3, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(True))
        self.layer1 = Res2NetBlock(32, 4)
        self.down = nn.Sequential(nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.BatchNorm2d(64), nn.ReLU(True))
        self.layer2 = Res2NetBlock(64, 4)
        self.head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(64, num_classes))

    def forward(self, x):
        return self.head(self.layer2(self.down(self.layer1(self.stem(x)))))


class DenseLayer(nn.Module):
    def __init__(self, in_ch, growth):
        super().__init__()
        self.net = nn.Sequential(nn.BatchNorm2d(in_ch), nn.ReLU(True), nn.Conv2d(in_ch, growth, 3, padding=1, bias=False))

    def forward(self, x):
        return torch.cat([x, self.net(x)], dim=1)


class MicroDenseNet(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.stem = nn.Conv2d(3, 24, 3, padding=1)
        channels, layers = 24, []
        for _ in range(4):
            layers.append(DenseLayer(channels, 12))
            channels += 12
        self.dense = nn.Sequential(*layers)
        self.trans = nn.Sequential(nn.BatchNorm2d(channels), nn.ReLU(True), nn.Conv2d(channels, 64, 1), nn.AvgPool2d(2))
        self.head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(64, num_classes))

    def forward(self, x):
        return self.head(self.trans(self.dense(self.stem(x))))


class DepthwiseBlock(nn.Module):
    def __init__(self, in_ch, out_ch, stride=1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, in_ch, 3, stride=stride, padding=1, groups=in_ch, bias=False), nn.BatchNorm2d(in_ch), nn.ReLU(True),
            nn.Conv2d(in_ch, out_ch, 1, bias=False), nn.BatchNorm2d(out_ch), nn.ReLU(True),
        )

    def forward(self, x):
        return self.net(x)


class MicroMobileNet(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1, bias=False), nn.BatchNorm2d(32), nn.ReLU(True),
            DepthwiseBlock(32, 64), DepthwiseBlock(64, 96, 2), DepthwiseBlock(96, 128, 2),
            nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(128, num_classes),
        )

    def forward(self, x):
        return self.net(x)


@torch.no_grad()
def evaluate(model, loader):
    model.eval()
    loss_sum = total = correct = 0
    y_true, y_pred = [], []
    for x, y in loader:
        x, y = x.to(DEVICE), y.to(DEVICE)
        logits = model(x)
        loss_sum += F.cross_entropy(logits, y).item() * y.size(0)
        pred = logits.argmax(1)
        total += y.size(0)
        correct += (pred == y).sum().item()
        y_true.extend(y.cpu().tolist())
        y_pred.extend(pred.cpu().tolist())
    return loss_sum / total, correct / total, y_true, y_pred


def train(model, train_loader, val_loader, epochs=50, patience=8):
    model.to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=5e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    best_loss, bad_epochs = float("inf"), 0
    best_state = copy.deepcopy(model.state_dict())
    rows = []
    for epoch in loop(range(1, epochs + 1), desc=model.__class__.__name__, unit="epoch"):
        model.train()
        loss_sum = total = 0
        for x, y in loop(train_loader, desc=f"epoch {epoch}/{epochs}", leave=False):
            x, y = x.to(DEVICE), y.to(DEVICE)
            opt.zero_grad(set_to_none=True)
            loss = F.cross_entropy(model(x), y)
            loss.backward()
            opt.step()
            loss_sum += loss.item() * y.size(0)
            total += y.size(0)
        val_loss, val_acc, _, _ = evaluate(model, val_loader)
        if val_loss < best_loss - 1e-4:
            best_loss, bad_epochs, best_state = val_loss, 0, copy.deepcopy(model.state_dict())
        else:
            bad_epochs += 1
        early_stop = bad_epochs >= patience
        rows.append({"epoch": epoch, "train_loss": loss_sum / total, "val_loss": val_loss, "val_accuracy": val_acc, "lr": opt.param_groups[0]["lr"], "best_val_loss": best_loss, "early_stop": early_stop})
        scheduler.step()
        if early_stop:
            break
    model.load_state_dict(best_state)
    return rows


def main() -> None:
    random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    ensure(OUT)
    train_tf = T.Compose([T.RandomCrop(32, padding=4), T.RandomHorizontalFlip(), T.ToTensor(), T.Normalize((0.5,) * 3, (0.5,) * 3)])
    test_tf = T.Compose([T.ToTensor(), T.Normalize((0.5,) * 3, (0.5,) * 3)])
    train_ds = torchvision.datasets.CIFAR10(root=DATA_ROOT, train=True, download=True, transform=train_tf)
    test_ds = torchvision.datasets.CIFAR10(root=DATA_ROOT, train=False, download=True, transform=test_tf)
    train_loader = DataLoader(train_ds, batch_size=128, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(test_ds, batch_size=256, shuffle=False, num_workers=0, pin_memory=True)
    sample, _ = next(iter(DataLoader(test_ds, batch_size=32, shuffle=False)))
    save_image(sample * 0.5 + 0.5, OUT / "cifar10_samples.png", nrow=8)
    models = {"SimpleCNN": SimpleCNN(), "MicroResNet": MicroResNet(), "MicroRes2Net": MicroRes2Net(), "MicroDenseNet": MicroDenseNet(), "MicroMobileNet": MicroMobileNet()}
    summary, structures = [], [f"device: {DEVICE}", "dataset: CIFAR-10", "train_samples: 50000", "test_samples: 10000", "epochs: 50", "early_stopping: patience=8", ""]
    labels = list(train_ds.classes)
    for name, model in models.items():
        start = time.time()
        rows = train(model, train_loader, val_loader)
        val_loss, acc, y_true, y_pred = evaluate(model, val_loader)
        write_csv(OUT / f"{name}_metrics.csv", [{"model": name, **r} for r in rows])
        save_confusion(OUT / f"{name}_confusion.csv", confusion_matrix(y_true, y_pred, 10), labels)
        summary.append({"model": name, "val_loss": val_loss, "val_accuracy": acc, "seconds": round(time.time() - start, 2)})
        structures.extend([f"===== {name} =====", str(model), ""])
    write_csv(OUT / "cnn_summary.csv", summary)
    (OUT / "network_structures.txt").write_text("\n".join(structures), encoding="utf-8")


if __name__ == "__main__":
    main()
