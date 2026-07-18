"""Evaluation entrypoint."""

import argparse
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from config import DEFAULTS
from datasets.ecssd import ECSSDDataset
from engine.evaluator import evaluate
from model import available_models, build_model
from utils.device import maybe_wrap_data_parallel, resolve_runtime_device, unwrap_model
from utils.io import append_csv_row, load_checkpoint, load_state_dict_compat, make_timestamp, save_json


def build_parser():
    parser = argparse.ArgumentParser(description="Evaluate a saliency detection model.")
    parser.add_argument("--data-root", default=DEFAULTS["data_root"])
    parser.add_argument("--split-file", default=DEFAULTS["split_file"])
    parser.add_argument("--model", default=DEFAULTS["model"], choices=available_models())
    parser.add_argument("--image-size", type=int, default=DEFAULTS["image_size"])
    parser.add_argument("--batch-size", type=int, default=DEFAULTS["batch_size"])
    parser.add_argument("--num-workers", type=int, default=DEFAULTS["num_workers"])
    parser.add_argument("--device", default=DEFAULTS["device"])
    parser.add_argument("--gpu-ids", default=DEFAULTS["gpu_ids"])
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--pretrained", action="store_true")
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
    parser.add_argument("--zoom-topk", type=int, default=DEFAULTS["zoom_topk"])
    parser.add_argument("--zoom-patch-size", type=int, default=DEFAULTS["zoom_patch_size"])
    parser.add_argument("--zoom-grid-size", type=int, default=DEFAULTS["zoom_grid_size"])
    parser.add_argument("--zoom-coarse-weight", type=float, default=DEFAULTS["zoom_coarse_weight"])
    parser.add_argument("--zoom-patch-weight", type=float, default=DEFAULTS["zoom_patch_weight"])
    parser.add_argument("--zoom-delta-weight", type=float, default=DEFAULTS["zoom_delta_weight"])
    parser.add_argument("--zoom-side-weight", type=float, default=DEFAULTS["zoom_side_weight"])
    parser.add_argument("--zoom-loss", default=DEFAULTS["zoom_loss"], choices=["bce", "hybrid"])
    parser.add_argument("--disable-zoom-coarse-channel", action="store_true")
    parser.add_argument("--hybrid-edge-channels", type=int, default=128)
    parser.add_argument("--hybrid-edge-weight", type=float, default=1.0)
    parser.add_argument("--hybrid-side-weight", type=float, default=0.5)
    parser.add_argument("--f3net-variant", default="base", choices=["base", "enhanced"], help="F3Net variant: base or enhanced.")
    parser.add_argument("--f3net-loss-profile", default="base", choices=["base", "enhanced"], help="F3Net loss profile.")
    parser.add_argument("--sinet-channel", type=int, default=32, help="SINet-R18 internal channel count.")
    # C3Net-R18 ablation flags (must mirror train.py so the eval architecture matches the checkpoint).
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
    parser.add_argument("--tta", action="store_true", help="Test-time augmentation: average over scales x h-flip.")
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


def resolve_model_kwargs(args):
    kwargs = {"pretrained": args.pretrained}
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
    elif args.model == "resnet18_bbox_refine_mask":
        kwargs.update(
            patch_size=args.zoom_patch_size,
            coarse_loss_weight=args.zoom_coarse_weight,
            patch_loss_weight=args.zoom_patch_weight,
            delta_loss_weight=args.zoom_delta_weight,
            loss_type=args.zoom_loss,
        )
    elif args.model in {
        "resnet18_uncertainty_zoom_fullrefine",
        "resnet18_uncertainty_zoom",
        "resnet18_uncertainty_zoom_gated_ds_c1",
        "resnet18_uncertainty_zoom_gated_ds",
        "resnet18_uncertainty_zoom_gated_ds_wide",
    }:
        kwargs.update(
            zoom_topk=args.zoom_topk,
            patch_size=args.zoom_patch_size,
            grid_size=args.zoom_grid_size,
            coarse_loss_weight=args.zoom_coarse_weight,
            patch_loss_weight=args.zoom_patch_weight,
            delta_loss_weight=args.zoom_delta_weight,
            side_loss_weight=args.zoom_side_weight,
            loss_type=args.zoom_loss,
            use_coarse_channel=not args.disable_zoom_coarse_channel,
        )
    elif args.model in {"poolnet_uncertainty_route_r18", "poolnet_uncertainty_route_boundary_r18"}:
        kwargs.update(
            edge_channels=args.hybrid_edge_channels,
            edge_loss_weight=args.hybrid_edge_weight,
            aux_loss_weight=args.hybrid_side_weight,
            coarse_loss_weight=args.zoom_coarse_weight,
            loss_type=args.zoom_loss,
        )
    elif args.model == "poolnet_uncertainty_detail_route_r18":
        kwargs.update(
            edge_channels=args.hybrid_edge_channels,
            edge_loss_weight=args.hybrid_edge_weight,
            detail_loss_weight=args.hybrid_side_weight,
            coarse_loss_weight=args.zoom_coarse_weight,
            loss_type=args.zoom_loss,
            detail_kernel=args.ldf_detail_kernel,
        )
    elif args.model in {"poolnet_uncertainty_route_psg_r18", "poolnet_uncertainty_route_psg_consistency_r18"}:
        kwargs.update(
            edge_channels=args.hybrid_edge_channels,
            edge_loss_weight=args.hybrid_edge_weight,
            aux_loss_weight=args.hybrid_side_weight,
            coarse_loss_weight=args.zoom_coarse_weight,
            loss_type=args.zoom_loss,
        )
    elif args.model == "poolnet_uncertainty_route_boundary_lite_psg_r18":
        kwargs.update(
            edge_channels=args.hybrid_edge_channels,
            edge_loss_weight=args.hybrid_edge_weight,
            aux_loss_weight=args.hybrid_side_weight,
            coarse_loss_weight=args.zoom_coarse_weight,
            loss_type=args.zoom_loss,
        )
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
    dataset = ECSSDDataset(
        args.data_root,
        split=args.split,
        image_size=args.image_size,
        augment=False,
        split_file=args.split_file,
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)
    model = build_model(args.model, **resolve_model_kwargs(args))
    model = model.to(runtime_device)
    model, _used_gpu_ids = maybe_wrap_data_parallel(model, args.device, args.gpu_ids)

    map_location = runtime_device if runtime_device == "cpu" or torch.cuda.is_available() else "cpu"
    checkpoint = load_checkpoint(args.checkpoint, map_location=map_location)
    load_state_dict_compat(unwrap_model(model), checkpoint["model"])
    metrics = evaluate(model, loader, device=runtime_device, tta=args.tta)
    output_dir = Path(args.output_dir) if args.output_dir else Path(args.checkpoint).resolve().parent
    suffix = "_tta" if args.tta else ""

    summary_row = {
        "timestamp": make_timestamp(),
        "model": args.model,
        "checkpoint": str(Path(args.checkpoint)),
        "split": args.split,
        "image_size": args.image_size,
        "batch_size": args.batch_size,
        "device": runtime_device,
        "gpu_ids": args.gpu_ids,
        "mae": round(metrics["mae"], 6),
        "f_measure": round(metrics["f_measure"], 6),
        "max_f_measure": round(metrics["max_f_measure"], 6),
        "max_f_threshold": round(metrics["max_f_threshold"], 6),
        "s_measure": round(metrics["s_measure"], 6),
        "e_measure": round(metrics["e_measure"], 6),
        "pixel_acc": round(metrics["pixel_acc"], 6),
        "iou": round(metrics["iou"], 6),
    }
    for optional_key in (
        "coarse_mae",
        "coarse_f_measure",
        "coarse_max_f_measure",
        "coarse_max_f_threshold",
        "coarse_s_measure",
        "coarse_e_measure",
        "coarse_pixel_acc",
        "coarse_iou",
        "delta_mae",
        "delta_max_f",
        "delta_iou",
    ):
        if optional_key in metrics:
            summary_row[optional_key] = round(metrics[optional_key], 6)
    if args.tta:
        summary_row["tta"] = True
    save_json(summary_row, output_dir / f"{args.split}_metrics{suffix}.json")
    append_csv_row(output_dir.parent / f"{args.split}_summary{suffix}.csv", summary_row)
    print(
        f"mae={metrics['mae']:.4f} "
        f"f_measure@0.5={metrics['f_measure']:.4f} "
        f"max_f_measure={metrics['max_f_measure']:.4f} "
        f"max_f_threshold={metrics['max_f_threshold']:.4f} "
        f"s_measure={metrics['s_measure']:.4f} "
        f"e_measure={metrics['e_measure']:.4f} "
        f"pixel_acc={metrics['pixel_acc']:.4f} "
        f"iou={metrics['iou']:.4f}"
    )
    if "coarse_max_f_measure" in metrics:
        print(
            f" coarse_max_f_measure={metrics['coarse_max_f_measure']:.4f}"
            f" delta_max_f={metrics['delta_max_f']:.4f}"
            f" delta_iou={metrics['delta_iou']:.4f}"
        )


if __name__ == "__main__":
    main()
