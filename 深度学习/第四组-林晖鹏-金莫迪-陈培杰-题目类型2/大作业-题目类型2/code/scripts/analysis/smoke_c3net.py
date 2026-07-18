"""Quick smoke test for C3Net-R18: forward/backward over all ablation configs."""

import torch

from model import available_models, build_model

assert "c3net_r18" in available_models(), "c3net_r18 not registered"

x = torch.randn(2, 3, 352, 352)
mask = (torch.rand(2, 1, 352, 352) > 0.5).float()

configs = [
    {},
    {"use_context": False},
    {"use_edge": False},
    {"use_deep_supervision": False},
    {"use_cscm": False},
    {"loss_type": "bce", "use_context": False, "use_edge": False,
     "use_deep_supervision": False, "use_cscm": False},
    {"cscm_scales": (7,)},
    {"cscm_residual": False},
    {"cscm_variant": "norm"},                 # B2: local contrast normalization
    {"cscm_mode": "inject"},                   # B1: residual contrast injection
    {"cscm_mode": "inject", "cscm_variant": "norm", "cscm_gamma": 2.0},  # B1+B2 combined
    {"cscm_gate": "uncertainty"},              # UG-CSCM: uncertainty-gated contrast
    {"cscm_gate": "uncertainty", "loss_type": "bce", "use_context": False,
     "use_edge": False, "use_deep_supervision": False},  # UG-CSCM on a lean base
    {"loss_type": "hybrid"},                   # Hybrid loss (BCE+IoU+SSIM)
    {"use_body_detail": True, "loss_type": "hybrid"},  # body/detail supervision + hybrid
    {"use_body_detail": True, "loss_type": "hybrid", "use_context": False,
     "use_edge": False, "use_deep_supervision": False, "use_cscm": False},  # supervision-only
]

for cfg in configs:
    model = build_model("c3net_r18", pretrained=False, **cfg)
    model.train()
    out = model(x)
    loss = model.compute_loss(out, mask)
    loss.backward()
    model.eval()
    with torch.no_grad():
        ev = model(x)
    n_params = sum(p.numel() for p in model.parameters())
    aux = sorted(k for k in out if k != "pred")
    pred_shape = tuple(out["pred"].shape)
    print(f"cfg={cfg} pred={pred_shape} aux={aux} "
          f"loss={loss.item():.4f} eval_keys={list(ev.keys())} params={n_params / 1e6:.2f}M")

print("SMOKE_OK")
