"""Inference entrypoint."""

import argparse
from pathlib import Path

from PIL import Image
import torch
import torch.nn.functional as F

from config import DEFAULTS
from datasets.transforms import build_image_transform
from engine.trainer import resolve_prediction_tensor
from model import available_models, build_model
from utils.device import maybe_wrap_data_parallel, resolve_runtime_device, unwrap_model
from utils.io import ensure_dir, load_checkpoint, load_state_dict_compat, save_prediction


def build_parser():
    parser = argparse.ArgumentParser(description="Run inference on one image or a directory.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", default="predictions")
    parser.add_argument("--model", default=DEFAULTS["model"], choices=available_models())
    parser.add_argument("--image-size", type=int, default=DEFAULTS["image_size"])
    parser.add_argument("--device", default=DEFAULTS["device"])
    parser.add_argument("--gpu-ids", default=DEFAULTS["gpu_ids"])
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--multicue-context-type", default="pool", choices=["pool", "cpfe", "proj"])
    parser.add_argument("--disable-multicue-context", action="store_true")
    parser.add_argument("--disable-multicue-edge", action="store_true")
    parser.add_argument("--disable-multicue-deepsup", action="store_true")
    parser.add_argument("--disable-multicue-refine", action="store_true")
    parser.add_argument("--multicue-edge-weight", type=float, default=0.2)
    parser.add_argument("--disable-ldf-deepsup", action="store_true")
    parser.add_argument("--disable-ldf-body-detail", action="store_true")
    parser.add_argument("--enable-ldf-gated-fusion", action="store_true")
    parser.add_argument("--ldf-detail-kernel", type=int, default=9)
    parser.add_argument("--ldf-side-weight", type=float, default=0.2)
    parser.add_argument("--ldf-body-weight", type=float, default=0.4)
    parser.add_argument("--ldf-detail-weight", type=float, default=0.4)
    parser.add_argument("--ldf-consistency-weight", type=float, default=0.0)
    parser.add_argument("--ldf-loss", default="hybrid", choices=["bce", "hybrid"])
    parser.add_argument("--f3net-variant", default="base", choices=["base", "enhanced"])
    parser.add_argument("--f3net-loss-profile", default="base", choices=["base", "enhanced"])
    parser.add_argument("--sinet-channel", type=int, default=32)
    parser.add_argument("--disable-c3net-context", action="store_true")
    parser.add_argument("--disable-c3net-edge", action="store_true")
    parser.add_argument("--disable-c3net-deepsup", action="store_true")
    parser.add_argument("--disable-c3net-cscm", action="store_true")
    parser.add_argument("--c3net-cscm-scales", default="3,7,11")
    parser.add_argument("--c3net-cscm-gating", default="residual", choices=["residual", "pure"])
    parser.add_argument("--c3net-cscm-variant", default="diff", choices=["diff", "norm"])
    parser.add_argument("--c3net-cscm-mode", default="gate", choices=["gate", "inject"])
    parser.add_argument("--c3net-cscm-gamma", type=float, default=1.0)
    parser.add_argument("--c3net-cscm-gate", default="none", choices=["none", "uncertainty", "edge"])
    parser.add_argument("--c3net-cscm-fixed", action="store_true")
    parser.add_argument("--c3net-cscm-sup-weight", type=float, default=0.0)
    parser.add_argument("--c3net-cscm-skip", action="store_true")
    parser.add_argument("--c3net-cscm-d3", action="store_true")
    parser.add_argument("--c3net-cscm-learn-surround", action="store_true")
    parser.add_argument("--c3net-coarse-weight", type=float, default=0.4)
    parser.add_argument("--c3net-loss", default="structure", choices=["bce", "structure", "hybrid"])
    parser.add_argument("--c3net-edge-weight", type=float, default=0.3)
    parser.add_argument("--c3net-side-weight", type=float, default=0.4)
    parser.add_argument("--c3net-use-body-detail", action="store_true")
    parser.add_argument("--c3net-detail-kernel", type=int, default=9)
    parser.add_argument("--c3net-body-weight", type=float, default=0.4)
    parser.add_argument("--c3net-detail-weight", type=float, default=0.4)
    parser.add_argument("--ctdnet-channels", type=int, default=64)
    parser.add_argument("--disable-ctdnet-semantic", action="store_true")
    parser.add_argument("--disable-ctdnet-boundary", action="store_true")
    parser.add_argument("--disable-ctdnet-cam", action="store_true")
    parser.add_argument("--ctdnet-use-cscm", action="store_true")
    parser.add_argument("--ctdnet-loss", default="structure", choices=["bce", "structure", "hybrid"])
    parser.add_argument("--ctdnet-side-weight", type=float, default=0.4)
    parser.add_argument("--ctdnet-edge-weight", type=float, default=0.3)
    return parser


def iter_image_paths(path):
    path = Path(path)
    if path.is_file():
        return [path]
    return sorted([item for item in path.iterdir() if item.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}])


def resolve_model_kwargs(args):
    kwargs = {"pretrained": False}
    if args.model == "resnet18_multicue":
        kwargs.update(
            use_context=not args.disable_multicue_context,
            context_type="proj" if args.disable_multicue_context else args.multicue_context_type,
            use_edge=not args.disable_multicue_edge,
            use_deep_supervision=not args.disable_multicue_deepsup,
            use_edge_refine=not args.disable_multicue_refine,
            edge_loss_weight=args.multicue_edge_weight,
        )
    elif args.model == "resnet18_ldf_lite":
        kwargs.update(
            use_deep_supervision=not args.disable_ldf_deepsup,
            use_body_detail=not args.disable_ldf_body_detail,
            use_gated_fusion=args.enable_ldf_gated_fusion,
            detail_kernel=args.ldf_detail_kernel,
            side_loss_weight=args.ldf_side_weight,
            body_loss_weight=args.ldf_body_weight,
            detail_loss_weight=args.ldf_detail_weight,
            consistency_loss_weight=args.ldf_consistency_weight,
            loss_type=args.ldf_loss,
        )
    elif args.model == "f3net_r18":
        kwargs.update(variant=args.f3net_variant, loss_profile=args.f3net_loss_profile)
    elif args.model == "sinet_r18":
        kwargs.update(channel=args.sinet_channel)
    elif args.model == "c3net_r18":
        cscm_scales = tuple(int(s) for s in str(args.c3net_cscm_scales).split(",") if s.strip())
        kwargs.update(
            use_context=not args.disable_c3net_context,
            use_edge=not args.disable_c3net_edge,
            use_deep_supervision=not args.disable_c3net_deepsup,
            use_cscm=not args.disable_c3net_cscm,
            cscm_scales=cscm_scales,
            cscm_residual=args.c3net_cscm_gating == "residual",
            cscm_variant=args.c3net_cscm_variant,
            cscm_mode=args.c3net_cscm_mode,
            cscm_gamma=args.c3net_cscm_gamma,
            cscm_gate=args.c3net_cscm_gate,
            cscm_fixed=args.c3net_cscm_fixed,
            cscm_sup_weight=args.c3net_cscm_sup_weight,
            use_cscm_skip=args.c3net_cscm_skip,
            use_cscm_d3=args.c3net_cscm_d3,
            cscm_learn_surround=args.c3net_cscm_learn_surround,
            coarse_loss_weight=args.c3net_coarse_weight,
            loss_type=args.c3net_loss,
            edge_loss_weight=args.c3net_edge_weight,
            side_loss_weight=args.c3net_side_weight,
            use_body_detail=args.c3net_use_body_detail,
            detail_kernel=args.c3net_detail_kernel,
            body_loss_weight=args.c3net_body_weight,
            detail_loss_weight=args.c3net_detail_weight,
        )
    elif args.model == "ctdnet_r18":
        kwargs.update(
            channels=args.ctdnet_channels,
            use_semantic=not args.disable_ctdnet_semantic,
            use_boundary=not args.disable_ctdnet_boundary,
            use_cam=not args.disable_ctdnet_cam,
            use_cscm=args.ctdnet_use_cscm,
            loss_type=args.ctdnet_loss,
            side_loss_weight=args.ctdnet_side_weight,
            edge_loss_weight=args.ctdnet_edge_weight,
        )
    return kwargs


def main():
    args = build_parser().parse_args()
    runtime_device = resolve_runtime_device(args.device, args.gpu_ids)
    model = build_model(args.model, **resolve_model_kwargs(args))
    model = model.to(runtime_device)
    model, _used_gpu_ids = maybe_wrap_data_parallel(model, args.device, args.gpu_ids)
    checkpoint = load_checkpoint(args.checkpoint, map_location=runtime_device if torch.cuda.is_available() else "cpu")
    load_state_dict_compat(unwrap_model(model), checkpoint["model"])
    model.eval()

    transform = build_image_transform(args.image_size)
    output_dir = Path(args.output_dir)
    ensure_dir(output_dir)

    with torch.no_grad():
        for image_path in iter_image_paths(args.input):
            image = Image.open(image_path).convert("RGB")
            original_size = image.size[::-1]
            image = image.resize((args.image_size, args.image_size), Image.BILINEAR)
            image_tensor = transform(image).unsqueeze(0).to(runtime_device)
            pred = torch.sigmoid(resolve_prediction_tensor(model(image_tensor)))[0]
            pred = F.interpolate(pred.unsqueeze(0), size=original_size, mode="bilinear", align_corners=False)[0]
            save_prediction(pred, output_dir / f"{Path(image_path).stem}.png")


if __name__ == "__main__":
    main()
