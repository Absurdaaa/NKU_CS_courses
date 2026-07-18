"""标准 FID 评估。

基于 pytorch-fid 的 Inception-V3 特征提取器（与论文一致的标准 FID 网络，
权重已离线缓存）+ 标准 Fréchet 距离。设计为「在线评估」：训练前用真实图
预先算一次统计量，训练过程中对生成图反复算 FID。

FID 越低越好；它衡量真实/生成图在 Inception 特征空间的分布距离，是 GAN
论文里选 checkpoint / 选超参的主流指标（loss 不反映样本质量）。
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import torch

from pytorch_fid.fid_score import calculate_frechet_distance
from pytorch_fid.inception import InceptionV3


class FIDEvaluator:
    """在线 FID 评估器。"""

    def __init__(self, device: torch.device, num_samples: int = 5000, batch_size: int = 256) -> None:
        self.device = device
        self.num_samples = num_samples
        self.batch_size = batch_size
        block_idx = InceptionV3.BLOCK_INDEX_BY_DIM[2048]
        self.model = InceptionV3([block_idx]).to(device).eval()
        for param in self.model.parameters():
            param.requires_grad_(False)
        self._real_mu: np.ndarray | None = None
        self._real_sigma: np.ndarray | None = None

    @staticmethod
    def _to_inception_input(images: torch.Tensor) -> torch.Tensor:
        """[-1,1] 的单/三通道图 -> Inception 期望的 [0,1] 三通道（内部会再 resize 到 299）。"""

        x = (images + 1.0) / 2.0
        x = x.clamp(0.0, 1.0)
        if x.size(1) == 1:
            x = x.repeat(1, 3, 1, 1)
        return x

    @torch.no_grad()
    def _features(self, images: torch.Tensor) -> np.ndarray:
        x = self._to_inception_input(images.to(self.device))
        feat = self.model(x)[0]  # (N, 2048, 1, 1)
        feat = feat.squeeze(3).squeeze(2)  # (N, 2048)
        return feat.cpu().numpy()

    @staticmethod
    def _stats(feats: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return feats.mean(axis=0), np.cov(feats, rowvar=False)

    @torch.no_grad()
    def set_real(self, loader) -> None:
        """用真实图（来自 dataloader，batch 为 {"images": ...} 字典）预算统计量。"""

        feats: list[np.ndarray] = []
        count = 0
        for batch in loader:
            feats.append(self._features(batch["images"]))
            count += batch["images"].size(0)
            if count >= self.num_samples:
                break
        stacked = np.concatenate(feats, axis=0)[: self.num_samples]
        self._real_mu, self._real_sigma = self._stats(stacked)

    @torch.no_grad()
    def compute(self, generator, noise_fn: Callable[[int], torch.Tensor]) -> float:
        """对生成器采样 num_samples 张并返回 FID。noise_fn(b) 应返回 b 个噪声（已在目标 device）。"""

        if self._real_mu is None:
            raise RuntimeError("FIDEvaluator.set_real() must be called before compute().")

        was_training = generator.training
        generator.eval()
        feats: list[np.ndarray] = []
        remaining = self.num_samples
        while remaining > 0:
            b = min(self.batch_size, remaining)
            fake = generator(noise_fn(b))
            feats.append(self._features(fake))
            remaining -= b
        if was_training:
            generator.train()

        stacked = np.concatenate(feats, axis=0)[: self.num_samples]
        mu, sigma = self._stats(stacked)
        return float(calculate_frechet_distance(self._real_mu, self._real_sigma, mu, sigma))
