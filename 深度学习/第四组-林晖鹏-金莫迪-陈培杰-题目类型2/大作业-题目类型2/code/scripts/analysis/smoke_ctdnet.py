"""Quick smoke test for CTDNet-R18: forward/backward over ablation configs."""

import torch

from model import available_models, build_model

assert "ctdnet_r18" in available_models(), "ctdnet_r18 not registered"

x = torch.randn(2, 3, 352, 352)
mask = (torch.rand(2, 1, 352, 352) > 0.5).float()

configs = [
    {},                                                   # full trilateral
    {"use_semantic": False},                              # no semantic path
    {"use_boundary": False},                              # no boundary path + BRM
    {"use_cam": False},                                   # plain fusion instead of CAM
    {"use_semantic": False, "use_boundary": False},       # spatial path only (lean base)
    {"loss_type": "hybrid"},
    {"loss_type": "bce"},
    {"channels": 32},                                     # lighter
]

for cfg in configs:
    model = build_model("ctdnet_r18", pretrained=False, **cfg)
    model.train()
    out = model(x)
    loss = model.compute_loss(out, mask)
    loss.backward()
    model.eval()
    with torch.no_grad():
        ev = model(x)
    n = sum(p.numel() for p in model.parameters())
    aux = sorted(k for k in out if k != "pred")
    print(f"cfg={cfg} pred={tuple(out['pred'].shape)} aux={aux} "
          f"loss={loss.item():.4f} eval_keys={list(ev.keys())} params={n / 1e6:.2f}M")

print("SMOKE_OK")
