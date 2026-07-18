from __future__ import annotations

import csv
import random
from pathlib import Path

import torch
import torch.nn as nn
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
OUT = ROOT / "GAN" / "results"
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


class MLPGenerator(nn.Module):
    def __init__(self, z_dim=100):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(z_dim, 128), nn.ReLU(True), nn.Linear(128, 784), nn.Tanh())

    def forward(self, z):
        return self.net(z).view(-1, 1, 28, 28)


class MLPDiscriminator(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Flatten(), nn.Linear(784, 128), nn.LeakyReLU(0.2, True), nn.Linear(128, 1), nn.Sigmoid())

    def forward(self, x):
        return self.net(x)


class DCGenerator(nn.Module):
    def __init__(self, z_dim=100):
        super().__init__()
        self.net = nn.Sequential(
            nn.ConvTranspose2d(z_dim, 64, 7, 1, 0, bias=False), nn.BatchNorm2d(64), nn.ReLU(True),
            nn.ConvTranspose2d(64, 32, 4, 2, 1, bias=False), nn.BatchNorm2d(32), nn.ReLU(True),
            nn.ConvTranspose2d(32, 1, 4, 2, 1, bias=False), nn.Tanh(),
        )

    def forward(self, z):
        return self.net(z.view(z.size(0), z.size(1), 1, 1))


class DCDiscriminator(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, 32, 4, 2, 1), nn.LeakyReLU(0.2, True),
            nn.Conv2d(32, 64, 4, 2, 1, bias=False), nn.BatchNorm2d(64), nn.LeakyReLU(0.2, True),
            nn.Flatten(), nn.Linear(64 * 7 * 7, 1), nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x)


def train_gan(G, D, loader, epochs: int, z_dim: int):
    G.to(DEVICE)
    D.to(DEVICE)
    opt_g = torch.optim.Adam(G.parameters(), lr=2e-4, betas=(0.5, 0.999))
    opt_d = torch.optim.Adam(D.parameters(), lr=2e-4, betas=(0.5, 0.999))
    criterion = nn.BCELoss()
    rows = []
    fixed = torch.randn(8, z_dim, device=DEVICE)
    for epoch in loop(range(1, epochs + 1), desc=G.__class__.__name__, unit="epoch"):
        for i, (real, _) in enumerate(loop(loader, desc=f"epoch {epoch}/{epochs}", leave=False), 1):
            real = real.to(DEVICE)
            b = real.size(0)
            real_label = torch.full((b, 1), 0.9, device=DEVICE)
            fake_label = torch.zeros(b, 1, device=DEVICE)
            opt_d.zero_grad(set_to_none=True)
            loss_real = criterion(D(real), real_label)
            z = torch.randn(b, z_dim, device=DEVICE)
            fake = G(z)
            loss_fake = criterion(D(fake.detach()), fake_label)
            loss_d = loss_real + loss_fake
            loss_d.backward()
            opt_d.step()
            opt_g.zero_grad(set_to_none=True)
            loss_g = criterion(D(fake), real_label)
            loss_g.backward()
            opt_g.step()
            if i % max(1, len(loader) // 8) == 0 or i == len(loader):
                rows.append({"epoch": epoch, "iter": i, "D_loss": loss_d.item(), "G_loss": loss_g.item()})
    return rows, fixed


@torch.no_grad()
def save_generated(G, z, path: Path, nrow=8):
    G.eval()
    imgs = (G(z).cpu() + 1) / 2
    save_image(imgs.clamp(0, 1), path, nrow=nrow)


def main() -> None:
    random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    ensure(OUT)
    transform = T.Compose([T.ToTensor(), T.Normalize((0.5,), (0.5,))])
    ds = torchvision.datasets.FashionMNIST(root=DATA_ROOT, train=True, download=True, transform=transform)
    loader = DataLoader(ds, batch_size=64, shuffle=True, num_workers=0, pin_memory=True, drop_last=True)
    real, _ = next(iter(loader))
    save_image(real[:64] * 0.5 + 0.5, OUT / "fashionmnist_real_samples.png", nrow=8)
    z_dim = 100
    models = {"MLP_GAN": (MLPGenerator(z_dim), MLPDiscriminator(), 30), "DCGAN": (DCGenerator(z_dim), DCDiscriminator(), 50)}
    all_rows, summary = [], [f"device: {DEVICE}", "dataset: FashionMNIST train full", "batch_size: 64", "z_dim: 100", "real_label_smoothing: 0.9", ""]
    fixed_noise = torch.randn(8, z_dim, device=DEVICE)
    for name, (G, D, epochs) in models.items():
        rows, _ = train_gan(G, D, loader, epochs, z_dim)
        write_csv(OUT / f"{name}_losses.csv", [{"model": name, **r} for r in rows])
        all_rows.extend({"model": name, **r} for r in rows)
        save_generated(G, fixed_noise, OUT / f"{name}_generated_8.png", nrow=8)
        summary.extend([f"===== {name} Generator =====", str(G), f"===== {name} Discriminator =====", str(D), ""])
        if name == "DCGAN":
            sweep = []
            for dim in [0, 3, 7, 21, 42]:
                for value in [-2.0, 0.0, 2.0]:
                    z = fixed_noise.clone()
                    z[:, dim] = value
                    sweep.append((G(z).cpu() + 1) / 2)
            save_image(torch.cat(sweep, dim=0).clamp(0, 1), OUT / "DCGAN_latent_sweep_15x8.png", nrow=8)
    write_csv(OUT / "gan_losses.csv", all_rows)
    (OUT / "network_structures.txt").write_text("\n".join(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
