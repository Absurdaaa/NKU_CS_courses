from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision.models import inception_v3
from torchvision.utils import make_grid, save_image

try:
    from torchvision.models import Inception_V3_Weights
except Exception:
    Inception_V3_Weights = None

try:
    import scipy.linalg as scipy_linalg

    _SCIPY_AVAILABLE = True
except Exception:
    scipy_linalg = None
    _SCIPY_AVAILABLE = False

try:
    from sklearn.manifold import TSNE
except Exception as exc:
    TSNE = None
    _TSNE_IMPORT_ERROR = exc

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from Datafactory import get_dataloader
from GAN import DCDiscriminator, DCGenerator, SimpleDiscriminator, SimpleGenerator

IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


@dataclass
class EvalConfig:
    """评估与可视化配置。"""

    latent_dim: int = 100
    num_samples: int = 5000
    tsne_samples: int = 1000
    tsne_perplexity: int = 30
    grid_size: int = 10


class _ForwardHook:
    def __init__(self, module: nn.Module) -> None:
        self.features: Optional[torch.Tensor] = None
        self._handle = module.register_forward_hook(self._hook_fn)

    def _hook_fn(self, _module: nn.Module, _inputs: Tuple[torch.Tensor, ...], output: torch.Tensor) -> None:
        self.features = output

    def close(self) -> None:
        self._handle.remove()


class InceptionFeatureExtractor:
    """从 Inception-V3 提取 avgpool 特征与分类 logits。"""

    def __init__(self, device: torch.device) -> None:
        if Inception_V3_Weights is not None:
            self.model = inception_v3(weights=Inception_V3_Weights.DEFAULT, aux_logits=True)
        else:
            self.model = inception_v3(pretrained=True, aux_logits=True)
        self.model.to(device).eval()
        self._hook = _ForwardHook(self.model.avgpool)
        self.device = device

    @torch.no_grad()
    def get_features_and_logits(self, images: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        # 将灰度图变为 Inception 所需的 3x299x299 输入
        images = preprocess_for_inception(images.to(self.device))
        logits = self.model(images)
        if isinstance(logits, (tuple, list)):
            logits = logits[0]
        features = self._hook.features
        if features is None:
            raise RuntimeError("Inception 特征未捕获，请检查 Hook。")
        features = torch.flatten(features, 1)
        return features.detach().cpu(), logits.detach().cpu()

    def close(self) -> None:
        self._hook.close()


class DiscriminatorFeatureExtractor:
    """从判别器倒数第二层提取特征。"""

    def __init__(self, discriminator: nn.Module, layer_name: Optional[str] = None) -> None:
        self.discriminator = discriminator
        if layer_name is None:
            layer_name = self._guess_layer_name(discriminator)
        if not hasattr(discriminator, layer_name):
            raise ValueError(f"判别器中不存在层: {layer_name}")
        self.layer = getattr(discriminator, layer_name)
        self._hook = _ForwardHook(self.layer)

    @staticmethod
    def _guess_layer_name(discriminator: nn.Module) -> str:
        if hasattr(discriminator, "blocks"):
            return "blocks"
        if hasattr(discriminator, "lrelu1"):
            return "lrelu1"
        raise ValueError("无法自动推断判别器倒数第二层，请手动指定 layer_name。")

    @torch.no_grad()
    def get_features(self, images: torch.Tensor) -> torch.Tensor:
        _ = self.discriminator(images)
        features = self._hook.features
        if features is None:
            raise RuntimeError("判别器特征未捕获，请检查 Hook。")
        features = features.view(features.size(0), -1)
        return features.detach().cpu()

    def close(self) -> None:
        self._hook.close()


def preprocess_for_inception(images: torch.Tensor) -> torch.Tensor:
    """将 1x28x28 灰度图转换为 Inception-V3 需要的输入格式。"""

    # 将 [-1, 1] 还原到 [0, 1]
    images = (images + 1.0) / 2.0
    images = images.clamp(0.0, 1.0)

    # 通道复制：1 -> 3
    images = images.repeat(1, 3, 1, 1)

    # 双线性插值到 299x299
    images = F.interpolate(images, size=(299, 299), mode="bilinear", align_corners=False)

    # ImageNet 标准化
    mean = IMAGENET_MEAN.to(images.device)
    std = IMAGENET_STD.to(images.device)
    images = (images - mean) / std
    return images


def sample_latent_noise(
    batch_size: int, latent_dim: int, is_dcgan: bool, device: torch.device
) -> torch.Tensor:
    """根据 GAN 类型生成潜向量噪声。"""

    z = torch.randn(batch_size, latent_dim, device=device)
    if is_dcgan:
        z = z.view(batch_size, latent_dim, 1, 1)
    return z


def _collect_inception_from_loader(
    data_loader: DataLoader,
    extractor: InceptionFeatureExtractor,
    num_samples: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    features_list = []
    logits_list = []
    total = 0

    for images, _ in data_loader:
        feats, logits = extractor.get_features_and_logits(images)
        features_list.append(feats)
        logits_list.append(logits)
        total += images.size(0)
        if total >= num_samples:
            break

    features = torch.cat(features_list, dim=0)[:num_samples]
    logits = torch.cat(logits_list, dim=0)[:num_samples]
    return features, logits


def _collect_inception_from_generator(
    generator: nn.Module,
    extractor: InceptionFeatureExtractor,
    num_samples: int,
    batch_size: int,
    latent_dim: int,
    is_dcgan: bool,
    device: torch.device,
) -> Tuple[torch.Tensor, torch.Tensor]:
    features_list = []
    logits_list = []
    total = 0
    generator.eval()

    while total < num_samples:
        cur_batch = min(batch_size, num_samples - total)
        z = sample_latent_noise(cur_batch, latent_dim, is_dcgan, device)
        with torch.no_grad():
            fake_images = generator(z)
        feats, logits = extractor.get_features_and_logits(fake_images)
        features_list.append(feats)
        logits_list.append(logits)
        total += cur_batch

    features = torch.cat(features_list, dim=0)[:num_samples]
    logits = torch.cat(logits_list, dim=0)[:num_samples]
    return features, logits


def _collect_features_from_loader(
    data_loader: DataLoader,
    feature_fn: Callable[[torch.Tensor], torch.Tensor],
    num_samples: int,
    device: torch.device,
) -> torch.Tensor:
    features_list = []
    total = 0

    for images, _ in data_loader:
        features = feature_fn(images.to(device))
        features_list.append(features)
        total += images.size(0)
        if total >= num_samples:
            break

    return torch.cat(features_list, dim=0)[:num_samples]


def _collect_features_from_generator(
    generator: nn.Module,
    feature_fn: Callable[[torch.Tensor], torch.Tensor],
    num_samples: int,
    batch_size: int,
    latent_dim: int,
    is_dcgan: bool,
    device: torch.device,
) -> torch.Tensor:
    features_list = []
    total = 0
    generator.eval()

    while total < num_samples:
        cur_batch = min(batch_size, num_samples - total)
        z = sample_latent_noise(cur_batch, latent_dim, is_dcgan, device)
        with torch.no_grad():
            fake_images = generator(z)
        features = feature_fn(fake_images)
        features_list.append(features)
        total += cur_batch

    return torch.cat(features_list, dim=0)[:num_samples]


def _covariance(features: torch.Tensor) -> torch.Tensor:
    features = features.double()
    mean = features.mean(dim=0, keepdim=True)
    centered = features - mean
    return (centered.t() @ centered) / (features.size(0) - 1)


def _sqrtm_psd(matrix: torch.Tensor) -> torch.Tensor:
    if _SCIPY_AVAILABLE:
        sqrtm = scipy_linalg.sqrtm(matrix.cpu().numpy())
        if np.iscomplexobj(sqrtm):
            sqrtm = sqrtm.real
        return torch.from_numpy(sqrtm).to(matrix.device, dtype=matrix.dtype)

    # 无 SciPy 时使用特征值分解近似
    sym = (matrix + matrix.t()) / 2.0
    eigvals, eigvecs = torch.linalg.eigh(sym)
    eigvals = torch.clamp(eigvals, min=0)
    return eigvecs @ torch.diag(torch.sqrt(eigvals)) @ eigvecs.t()


def calculate_fid(real_features: torch.Tensor, fake_features: torch.Tensor) -> float:
    """计算 FID 指标。"""

    if real_features.size(0) < 2 or fake_features.size(0) < 2:
        raise ValueError("FID 需要至少 2 个样本。")

    real_mu = real_features.mean(dim=0).double()
    fake_mu = fake_features.mean(dim=0).double()
    real_cov = _covariance(real_features)
    fake_cov = _covariance(fake_features)
    covmean = _sqrtm_psd(real_cov @ fake_cov)

    diff = real_mu - fake_mu
    fid = diff.dot(diff) + torch.trace(real_cov + fake_cov - 2.0 * covmean)
    return float(fid.item())


def calculate_inception_score(
    logits: torch.Tensor, splits: int = 10, eps: float = 1e-8
) -> Tuple[float, float]:
    """计算 Inception Score，返回均值与标准差。"""

    probs = torch.softmax(logits, dim=1)
    num_samples = probs.size(0)
    splits = max(1, min(splits, num_samples))
    scores = []

    for idx in range(splits):
        part = probs[idx * num_samples // splits : (idx + 1) * num_samples // splits]
        py = part.mean(dim=0, keepdim=True)
        kl = part * (torch.log(part + eps) - torch.log(py + eps))
        score = torch.exp(kl.sum(dim=1).mean())
        scores.append(score)

    scores = torch.stack(scores)
    return float(scores.mean().item()), float(scores.std().item())


def evaluate_fid_is(
    generator: nn.Module,
    data_loader: DataLoader,
    device: torch.device,
    is_dcgan: bool,
    latent_dim: int = 100,
    num_samples: int = 5000,
    splits: int = 10,
) -> Tuple[float, float, float]:
    """计算 FID 与 IS，并返回 (FID, IS均值, IS标准差)。"""

    extractor = InceptionFeatureExtractor(device)
    real_features, _ = _collect_inception_from_loader(data_loader, extractor, num_samples)
    num_real = real_features.size(0)
    batch_size = data_loader.batch_size or 256

    fake_features, fake_logits = _collect_inception_from_generator(
        generator,
        extractor,
        num_real,
        batch_size,
        latent_dim,
        is_dcgan,
        device,
    )
    extractor.close()

    fid = calculate_fid(real_features, fake_features)
    is_mean, is_std = calculate_inception_score(fake_logits, splits=splits)
    return fid, is_mean, is_std


def tsne_real_fake(
    generator: nn.Module,
    data_loader: DataLoader,
    device: torch.device,
    is_dcgan: bool,
    num_samples: int = 1000,
    latent_dim: int = 100,
    feature_source: str = "inception",
    discriminator: Optional[nn.Module] = None,
    save_path: str = "tsne_real_fake.png",
    perplexity: int = 30,
    random_state: int = 42,
) -> None:
    """使用 t-SNE 绘制真实与生成样本的特征分布。"""

    if TSNE is None:
        raise ImportError(f"缺少 scikit-learn: {_TSNE_IMPORT_ERROR}")

    batch_size = data_loader.batch_size or 256

    if feature_source == "inception":
        extractor = InceptionFeatureExtractor(device)
        real_features, _ = _collect_inception_from_loader(data_loader, extractor, num_samples)
        num_real = real_features.size(0)
        fake_features, _ = _collect_inception_from_generator(
            generator,
            extractor,
            num_real,
            batch_size,
            latent_dim,
            is_dcgan,
            device,
        )
        extractor.close()
    elif feature_source == "discriminator":
        if discriminator is None:
            raise ValueError("使用判别器特征时必须传入 discriminator。")
        discriminator.eval()
        feature_extractor = DiscriminatorFeatureExtractor(discriminator)
        real_features = _collect_features_from_loader(
            data_loader,
            feature_extractor.get_features,
            num_samples,
            device,
        )
        num_real = real_features.size(0)
        fake_features = _collect_features_from_generator(
            generator,
            feature_extractor.get_features,
            num_real,
            batch_size,
            latent_dim,
            is_dcgan,
            device,
        )
        feature_extractor.close()
    else:
        raise ValueError("feature_source 仅支持 'inception' 或 'discriminator'。")

    all_features = torch.cat([real_features, fake_features], dim=0).numpy()
    labels = np.array([0] * real_features.size(0) + [1] * fake_features.size(0))

    total = all_features.shape[0]
    max_perp = max(5, (total - 1) // 3)
    use_perp = min(perplexity, max_perp)

    tsne = TSNE(
        n_components=2,
        perplexity=use_perp,
        random_state=random_state,
        init="pca",
        learning_rate="auto",
    )
    embed = tsne.fit_transform(all_features)

    real_embed = embed[labels == 0]
    fake_embed = embed[labels == 1]

    plt.figure(figsize=(7, 6))
    plt.scatter(real_embed[:, 0], real_embed[:, 1], s=10, c="tab:blue", alpha=0.6, label="Real")
    plt.scatter(fake_embed[:, 0], fake_embed[:, 1], s=10, c="tab:orange", alpha=0.6, label="Fake")
    plt.legend()
    plt.title("t-SNE: Real vs Fake")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def latent_manifold_traversal_2d(
    generator: nn.Module,
    device: torch.device,
    latent_dim: int = 100,
    grid_size: int = 10,
    value_range: Tuple[float, float] = (-2.0, 2.0),
    dims: Tuple[int, int] = (0, 1),
    is_dcgan: bool = False,
    save_path: str = "latent_traversal.png",
    fixed_seed: Optional[int] = 123,
) -> None:
    """固定其余潜向量维度，遍历二维网格并保存结果图。"""

    generator.eval()

    if fixed_seed is not None:
        rng = torch.Generator(device=device).manual_seed(fixed_seed)
        base_z = torch.randn(latent_dim, generator=rng, device=device)
    else:
        base_z = torch.randn(latent_dim, device=device)

    values = torch.linspace(value_range[0], value_range[1], grid_size, device=device)
    z_list = []

    for y in values:
        for x in values:
            z = base_z.clone()
            z[dims[0]] = x
            z[dims[1]] = y
            z_list.append(z)

    z_batch = torch.stack(z_list, dim=0)
    if is_dcgan:
        z_batch = z_batch.view(z_batch.size(0), latent_dim, 1, 1)

    with torch.no_grad():
        images = generator(z_batch).cpu()
    images = (images + 1.0) / 2.0
    images = images.clamp(0.0, 1.0)

    grid = make_grid(images, nrow=grid_size, padding=2)
    save_image(grid, save_path)


def _load_weights(model: nn.Module, weight_path: str, device: torch.device) -> None:
    state_dict = torch.load(weight_path, map_location=device)
    model.load_state_dict(state_dict)


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _, test_loader = get_dataloader()
    cfg = EvalConfig()

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # SimpleGAN 示例
    simple_g = SimpleGenerator().to(device)
    simple_d = SimpleDiscriminator().to(device)
    _load_weights(simple_g, os.path.join(base_dir, "SimpleGAN_generator.pth"), device)
    _load_weights(simple_d, os.path.join(base_dir, "SimpleGAN_discriminator.pth"), device)

    fid, is_mean, is_std = evaluate_fid_is(
        simple_g,
        test_loader,
        device,
        is_dcgan=False,
        latent_dim=cfg.latent_dim,
        num_samples=cfg.num_samples,
        splits=10,
    )
    print(f"[SimpleGAN] FID={fid:.4f}, IS={is_mean:.4f} ± {is_std:.4f}")

    tsne_real_fake(
        generator=simple_g,
        data_loader=test_loader,
        device=device,
        is_dcgan=False,
        num_samples=cfg.tsne_samples,
        latent_dim=cfg.latent_dim,
        feature_source="inception",
        discriminator=simple_d,
        perplexity=cfg.tsne_perplexity,
        save_path=os.path.join(base_dir, "tsne_simplegan.png"),
    )

    latent_manifold_traversal_2d(
        generator=simple_g,
        device=device,
        latent_dim=cfg.latent_dim,
        grid_size=cfg.grid_size,
        is_dcgan=False,
        save_path=os.path.join(base_dir, "simplegan_manifold.png"),
    )

    # DCGAN 示例
    dc_g = DCGenerator().to(device)
    dc_d = DCDiscriminator().to(device)
    _load_weights(dc_g, os.path.join(base_dir, "DCGAN_generator.pth"), device)
    _load_weights(dc_d, os.path.join(base_dir, "DCGAN_discriminator.pth"), device)

    fid, is_mean, is_std = evaluate_fid_is(
        dc_g,
        test_loader,
        device,
        is_dcgan=True,
        latent_dim=cfg.latent_dim,
        num_samples=cfg.num_samples,
        splits=10,
    )
    print(f"[DCGAN] FID={fid:.4f}, IS={is_mean:.4f} ± {is_std:.4f}")

    tsne_real_fake(
        generator=dc_g,
        data_loader=test_loader,
        device=device,
        is_dcgan=True,
        num_samples=cfg.tsne_samples,
        latent_dim=cfg.latent_dim,
        feature_source="inception",
        discriminator=dc_d,
        perplexity=cfg.tsne_perplexity,
        save_path=os.path.join(base_dir, "tsne_dcgan.png"),
    )

    latent_manifold_traversal_2d(
        generator=dc_g,
        device=device,
        latent_dim=cfg.latent_dim,
        grid_size=cfg.grid_size,
        is_dcgan=True,
        save_path=os.path.join(base_dir, "dcgan_manifold.png"),
    )


if __name__ == "__main__":
    main()
