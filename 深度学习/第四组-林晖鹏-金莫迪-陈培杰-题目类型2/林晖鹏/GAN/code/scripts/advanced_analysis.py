#!/usr/bin/env python3
"""Lab4 进阶分析：潜空间插值、多样性/模式崩溃、最近邻过拟合检验、判别器特征分类。

四个实验大多基于已训好的 best_model.pth（②④需少量训练）。
结果图写入 实验模板/fig/generated/，数值打印并写入 实验模板/tables/advanced_metrics.txt。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import build_model
from src.utils.runtime import set_seed, setup_matplotlib

setup_matplotlib(PROJECT_ROOT)

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torchvision
import torchvision.utils as vutils
from torchvision import transforms

FIG_ROOT = PROJECT_ROOT / "实验模板" / "fig" / "generated"
TABLE_ROOT = PROJECT_ROOT / "实验模板" / "tables"
OUT_ROOT = PROJECT_ROOT / "outputs"
DATA_ROOT = PROJECT_ROOT / "data"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MODELS = [
    ("gan", "final_gan_fashionmnist"),
    ("gan_deep", "final_gan_deep_fashionmnist"),
    ("dcgan", "final_dcgan_fashionmnist"),
]
CLASS_NAMES = ["T-shirt", "Trouser", "Pullover", "Dress", "Coat",
               "Sandal", "Shirt", "Sneaker", "Bag", "Ankle boot"]

_LOG_LINES: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)
    _LOG_LINES.append(msg)


# --------------------------- 公共工具 ---------------------------
def load_generator_discriminator(model: str, run: str):
    run_dir = OUT_ROOT / model / run
    meta = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    ckpt = torch.load(run_dir / "best_model.pth", map_location=DEVICE)
    generator, discriminator = build_model(
        model,
        latent_dim=int(meta["latent_dim"]),
        hidden_dim=int(meta.get("hidden_dim", 128)),
        image_size=int(meta["image_size"]),
        image_channels=int(meta["image_channels"]),
        generator_base_channels=int(meta.get("generator_base_channels", 64)),
        discriminator_base_channels=int(meta.get("discriminator_base_channels", 64)),
    )
    generator.load_state_dict(ckpt["generator_state_dict"])
    discriminator.load_state_dict(ckpt["discriminator_state_dict"])
    return generator.to(DEVICE).eval(), discriminator.to(DEVICE).eval(), int(meta["latent_dim"])


def to_model_noise(model: str, z: torch.Tensor) -> torch.Tensor:
    if model == "dcgan":
        return z.view(z.size(0), z.size(1), 1, 1)
    return z


def real_loader(train: bool, batch_size: int = 256):
    tfm = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.5,), (0.5,))])
    ds = torchvision.datasets.FashionMNIST(str(DATA_ROOT), train=train, download=False, transform=tfm)
    return torch.utils.data.DataLoader(ds, batch_size=batch_size, shuffle=train, num_workers=4)


def save_grid(images: torch.Tensor, path: Path, nrow: int, title: str | None = None) -> None:
    grid = vutils.make_grid(images.detach().cpu(), nrow=nrow, normalize=True, pad_value=0.3)
    fig = plt.figure(figsize=(max(8, nrow), max(4, images.size(0) / max(nrow, 1))))
    plt.axis("off")
    if title:
        plt.title(title)
    plt.imshow(grid.permute(1, 2, 0).numpy(), cmap="gray")
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


# --------------------------- 实验①：潜空间插值 ---------------------------
def find_endpoint(generator, model: str, clf, targets: set, z_dim: int, gen,
                  max_try: int = 600, conf: float = 0.8):
    """采样噪声，返回 (z, 预测类别, 置信度)：优先返回 targets 中置信度≥conf 的端点；
    否则返回 targets 中置信度最高的；若完全没采到 targets 类别（如模式崩溃），返回最后一个样本。"""
    best_z, best_pred, best_conf = None, -1, -1.0
    last = torch.randn(1, z_dim, generator=gen)
    with torch.no_grad():
        for _ in range(max_try):
            z = torch.randn(1, z_dim, generator=gen)
            img = generator(to_model_noise(model, z.to(DEVICE)))
            prob = torch.softmax(clf(img), dim=1)[0]
            pred = int(prob.argmax().item())
            if pred in targets:
                p = float(prob[pred].item())
                if p >= conf:
                    return z.squeeze(0), pred, p
                if p > best_conf:
                    best_z, best_pred, best_conf = z.squeeze(0), pred, p
            last = z
    if best_z is not None:
        return best_z, best_pred, best_conf
    return last.squeeze(0), -1, 0.0


def exp_interpolation(clf, steps: int = 10) -> None:
    """每个模型取一组端点（鞋 -> 上衣/裤子），线性插值 steps 步；三个模型堆成 3xsteps 组图。"""
    log("\n[①潜空间插值]")
    shoes = {5, 7, 9}          # Sandal / Sneaker / Ankle boot
    clothes = {1, 2, 3, 4, 6}  # Trouser / Pullover / Dress / Coat / Shirt
    clf.eval()
    rows = []
    for model, run in MODELS:
        try:
            generator, _, z_dim = load_generator_discriminator(model, run)
        except FileNotFoundError:
            log(f"  跳过 {model}（无 checkpoint）")
            continue
        gen = torch.Generator().manual_seed(2024)
        z0, c0, p0 = find_endpoint(generator, model, clf, shoes, z_dim, gen)
        z1, c1, p1 = find_endpoint(generator, model, clf, clothes, z_dim, gen)
        n0 = CLASS_NAMES[c0] if c0 >= 0 else "无(崩溃)"
        n1 = CLASS_NAMES[c1] if c1 >= 0 else "无(崩溃)"
        log(f"  {model}: 端点 z0={n0}(conf={p0:.2f}) -> z1={n1}(conf={p1:.2f})")
        alphas = torch.linspace(0, 1, steps)
        with torch.no_grad():
            for a in alphas:
                zi = ((1 - a) * z0 + a * z1).unsqueeze(0).to(DEVICE)
                rows.append(generator(to_model_noise(model, zi)).cpu())
    if rows:
        save_grid(torch.cat(rows, 0), FIG_ROOT / "interpolation_grid.png", nrow=steps)
        log("  已保存 interpolation_grid.png（每行一个模型）")


# --------------------------- 分类器（用于②多样性） ---------------------------
class SmallCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Flatten(), nn.Linear(64 * 7 * 7, 128), nn.ReLU(), nn.Linear(128, 10),
        )

    def forward(self, x):
        return self.net(x)


def train_classifier(epochs: int = 3) -> SmallCNN:
    log("\n[训练 FashionMNIST 分类器（②的裁判）]")
    clf = SmallCNN().to(DEVICE)
    opt = torch.optim.Adam(clf.parameters(), lr=1e-3)
    crit = nn.CrossEntropyLoss()
    loader = real_loader(train=True)
    clf.train()
    for ep in range(epochs):
        correct = total = 0
        for x, y in loader:
            x, y = x.to(DEVICE), y.to(DEVICE)
            opt.zero_grad()
            out = clf(x)
            loss = crit(out, y)
            loss.backward()
            opt.step()
            correct += (out.argmax(1) == y).sum().item()
            total += y.size(0)
        log(f"  epoch {ep + 1}/{epochs} train_acc={correct / total:.4f}")
    # 测试准确率
    clf.eval()
    correct = total = 0
    with torch.no_grad():
        for x, y in real_loader(train=False):
            x, y = x.to(DEVICE), y.to(DEVICE)
            correct += (clf(x).argmax(1) == y).sum().item()
            total += y.size(0)
    log(f"  分类器测试准确率={correct / total:.4f}")
    return clf


# --------------------------- 实验②：多样性 / 模式崩溃 ---------------------------
def exp_diversity(clf: SmallCNN, n_samples: int = 5000) -> None:
    log("\n[②多样性 / 模式崩溃]")
    clf.eval()
    dist = {}
    for model, run in MODELS:
        try:
            generator, _, z_dim = load_generator_discriminator(model, run)
        except FileNotFoundError:
            continue
        counts = np.zeros(10, dtype=np.int64)
        gen = torch.Generator().manual_seed(123)
        done = 0
        with torch.no_grad():
            while done < n_samples:
                b = min(500, n_samples - done)
                z = torch.randn(b, z_dim, generator=gen).to(DEVICE)
                fake = generator(to_model_noise(model, z))
                pred = clf(fake).argmax(1).cpu().numpy()
                for p in pred:
                    counts[p] += 1
                done += b
        probs = counts / counts.sum()
        # 归一化熵（1=完全均匀；越低越崩溃）；覆盖类别数（占比>1%）
        ent = -np.sum(probs[probs > 0] * np.log(probs[probs > 0])) / np.log(10)
        coverage = int((probs > 0.01).sum())
        dist[model] = probs
        log(f"  {model}: 归一化熵={ent:.3f} 覆盖类别数={coverage}/10 "
            f"最多类={CLASS_NAMES[probs.argmax()]}({probs.max():.2f})")
    # 画类别分布雷达图：10 个类别为轴，每个模型一条闭合曲线
    angles = np.linspace(0, 2 * np.pi, 10, endpoint=False)
    angles_closed = np.concatenate([angles, angles[:1]])
    fig, ax = plt.subplots(figsize=(5.5, 5.5), subplot_kw={"polar": True})
    for model, _ in MODELS:
        if model in dist:
            vals = np.concatenate([dist[model], dist[model][:1]])
            ax.plot(angles_closed, vals, marker="o", markersize=3, label=model)
            ax.fill(angles_closed, vals, alpha=0.1)
    ax.set_xticks(angles)
    ax.set_xticklabels(CLASS_NAMES, fontsize=8)
    ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1.12), fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_ROOT / "diversity_class_distribution.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    log("  已保存 diversity_class_distribution.png（雷达图）")


# --------------------------- 实验③：最近邻过拟合检验 ---------------------------
def exp_nearest_neighbor(n_query: int = 6) -> None:
    log("\n[③最近邻过拟合检验]")
    # 取一批真实训练图作检索库
    real_imgs = []
    for x, _ in real_loader(train=True):
        real_imgs.append(x)
        if sum(t.size(0) for t in real_imgs) >= 12000:
            break
    real = torch.cat(real_imgs, 0)[:12000].to(DEVICE)
    real_flat = real.view(real.size(0), -1)
    for model, run in MODELS:
        try:
            generator, _, z_dim = load_generator_discriminator(model, run)
        except FileNotFoundError:
            continue
        gen = torch.Generator().manual_seed(7)
        z = torch.randn(n_query, z_dim, generator=gen).to(DEVICE)
        with torch.no_grad():
            fake = generator(to_model_noise(model, z))
        fakes, reals = [], []
        ff = fake.view(n_query, -1)
        for i in range(n_query):
            d = torch.cdist(ff[i:i + 1], real_flat)  # (1, N)
            nn_idx = d.argmin(1).item()
            fakes.append(fake[i:i + 1].cpu())
            reals.append(real[nn_idx:nn_idx + 1].cpu())
        # 上行：生成图；下行：对应的最近邻真实图（2 x n_query 横向排列）
        save_grid(torch.cat(fakes + reals, 0), FIG_ROOT / f"{model}_nearest_neighbor.png", nrow=n_query)
        log(f"  {model}: 已保存最近邻对照（上行生成/下行最近邻真实，{n_query} 列）")


# --------------------------- 实验④：判别器特征分类 ---------------------------
def extract_d_features(model: str, discriminator: nn.Module, x: torch.Tensor) -> torch.Tensor:
    """取判别器最后分类层之前的特征。"""
    if model == "gan":
        flat = x.view(x.size(0), -1)
        return discriminator.nonlin1(discriminator.fc1(flat))
    if model == "gan_deep":
        flat = x.view(x.size(0), -1)
        return discriminator.model[:-2](flat)  # 去掉 Linear(256,1)+Sigmoid
    # dcgan
    feat = discriminator.main[:-2](x)  # 去掉最后 Conv(->1)+Sigmoid
    return feat.view(feat.size(0), -1)


def linear_probe(feat_fn, feat_dim: int, tag: str, epochs: int = 5) -> float:
    """冻结特征，训练线性分类器，返回测试准确率。"""
    clf = nn.Linear(feat_dim, 10).to(DEVICE)
    opt = torch.optim.Adam(clf.parameters(), lr=1e-3)
    crit = nn.CrossEntropyLoss()
    for ep in range(epochs):
        for x, y in real_loader(train=True):
            x, y = x.to(DEVICE), y.to(DEVICE)
            with torch.no_grad():
                f = feat_fn(x)
            opt.zero_grad()
            loss = crit(clf(f), y)
            loss.backward()
            opt.step()
    correct = total = 0
    with torch.no_grad():
        for x, y in real_loader(train=False):
            x, y = x.to(DEVICE), y.to(DEVICE)
            correct += (clf(feat_fn(x)).argmax(1) == y).sum().item()
            total += y.size(0)
    acc = correct / total
    log(f"  {tag}: 线性探针测试准确率={acc:.4f} (特征维度={feat_dim})")
    return acc


def exp_discriminator_features() -> None:
    log("\n[④判别器特征分类（线性探针）]")
    # 原始像素 baseline
    linear_probe(lambda x: x.view(x.size(0), -1), 28 * 28, "raw-pixel baseline")
    for model, run in MODELS:
        try:
            _, discriminator, _ = load_generator_discriminator(model, run)
        except FileNotFoundError:
            continue
        # 探一次特征维度
        with torch.no_grad():
            sample = next(iter(real_loader(train=False)))[0][:8].to(DEVICE)
            feat_dim = extract_d_features(model, discriminator, sample).shape[1]
        # 训练好的判别器
        linear_probe(lambda x, m=model, d=discriminator: extract_d_features(m, d, x),
                     feat_dim, f"{model} trained-D")
        # 随机初始化判别器 baseline（同结构未训练）
        _, rand_d = build_model_for_random(model)
        linear_probe(lambda x, m=model, d=rand_d: extract_d_features(m, d, x),
                     feat_dim, f"{model} random-D baseline")


def build_model_for_random(model: str):
    _, d = build_model(model, latent_dim=100, image_size=28, image_channels=1)
    return None, d.to(DEVICE).eval()


# --------------------------- 主入口 ---------------------------
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp", nargs="+",
                        default=["interp", "diversity", "nn", "dfeat"],
                        help="要运行的实验子集")
    parser.add_argument("--gan-run", default="final_gan_fashionmnist")
    parser.add_argument("--gan-deep-run", default="final_gan_deep_fashionmnist")
    parser.add_argument("--dcgan-run", default="final_dcgan_fashionmnist")
    args = parser.parse_args()

    global MODELS
    MODELS = [("gan", args.gan_run), ("gan_deep", args.gan_deep_run), ("dcgan", args.dcgan_run)]
    set_seed(42)
    FIG_ROOT.mkdir(parents=True, exist_ok=True)
    TABLE_ROOT.mkdir(parents=True, exist_ok=True)

    clf = None
    if "interp" in args.exp or "diversity" in args.exp:
        clf = train_classifier()
    if "interp" in args.exp:
        exp_interpolation(clf)
    if "nn" in args.exp:
        exp_nearest_neighbor()
    if "diversity" in args.exp:
        exp_diversity(clf)
    if "dfeat" in args.exp:
        exp_discriminator_features()

    (TABLE_ROOT / "advanced_metrics.txt").write_text("\n".join(_LOG_LINES) + "\n", encoding="utf-8")
    log(f"\n指标已写入 {TABLE_ROOT / 'advanced_metrics.txt'}")


if __name__ == "__main__":
    main()
