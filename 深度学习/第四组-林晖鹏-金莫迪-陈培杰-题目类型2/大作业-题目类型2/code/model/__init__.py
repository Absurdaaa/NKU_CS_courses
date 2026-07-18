"""Model registry for the SOD code release."""

from model.resnet18 import build_model as build_resnet18
from model.c3net_r18 import build_model as build_c3net_r18
from model.ctdnet_r18 import build_model as build_ctdnet_r18
from model.egnet_r18 import build_model as build_egnet_r18
from model.pfa_r18 import build_model as build_pfa_r18
from model.poolnet_r18 import build_model as build_poolnet_r18
from model.sinet_r18 import build_model as build_sinet_r18
from model.dss_r18 import build_model as build_dss_r18
from model.f3net_r18 import build_model as build_f3net_r18

MODEL_REGISTRY = {
    "resnet18":   build_resnet18,
    "c3net_r18":  build_c3net_r18,
    "ctdnet_r18": build_ctdnet_r18,
    "egnet_r18":  build_egnet_r18,
    "pfa_r18":    build_pfa_r18,
    "poolnet_r18": build_poolnet_r18,
    "sinet_r18":  build_sinet_r18,
    "dss_r18":    build_dss_r18,
    "f3net_r18":  build_f3net_r18,
}


def build_model(name, **kwargs):
    if name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model '{name}'. Available: {sorted(MODEL_REGISTRY)}")
    return MODEL_REGISTRY[name](**kwargs)


def available_models():
    return sorted(MODEL_REGISTRY)
