"""随机种子、设备与 matplotlib 环境设置。"""

from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np
import torch


def setup_matplotlib(project_root: Path) -> None:
    matplotlib_dir = project_root / ".matplotlib"
    matplotlib_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(matplotlib_dir)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    # try:
    #     torch.use_deterministic_algorithms(True)
    # except Exception:
    #     pass
