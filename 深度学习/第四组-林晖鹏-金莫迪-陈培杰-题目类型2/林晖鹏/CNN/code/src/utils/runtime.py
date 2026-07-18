"""Runtime and reproducibility helpers."""

from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np
import torch


def setup_matplotlib(project_root: Path) -> None:
    cache_dir = project_root / ".matplotlib"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
    import matplotlib

    matplotlib.use("Agg")


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
