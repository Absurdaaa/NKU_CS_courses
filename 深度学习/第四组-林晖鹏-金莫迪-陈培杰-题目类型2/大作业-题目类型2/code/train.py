"""Training entrypoint for the rebuilt basic framework."""

import argparse
from pathlib import Path
import time

import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader

from config import DEFAULTS
from datasets.ecssd import ECSSDDataset
from engine.evaluator import evaluate
from engine.trainer import train_one_epoch
from model import available_models, build_model
from utils.device import maybe_wrap_data_parallel, resolve_runtime_device, unwrap_model
from utils.history import TrainingHistory
from utils.io import save_checkpoint, save_json, save_zoom_visualization
from utils.seed import set_seed


def build_parser():
    parser = argparse.ArgumentParser(description="Train a saliency detection model.")
    parser.add_argument("--data-root", default=DEFAULTS["data_root"])
    parser.add_argument("--split-file", default=DEFAULTS["split_file"])
    parser.add_argument("--model", default=DEFAULTS["model"], choices=available_models())
    parser.add_argument("--image-size", type=int, default=DEFAULTS["image_size"])
    parser.add_argument("--batch-size", type=int, default=DEFAULTS["batch_size"])
    parser.add_argument("--epochs", type=int, default=DEFAULTS["epochs"])
    parser.add_argument("--lr", type=float, default=DEFAULTS["lr"])
    parser.add_argument("--num-workers", type=int, default=DEFAULTS["num_workers"])
    parser.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    parser.add_argument("--device", default=DEFAULTS["device"])
    parser.add_argument("--gpu-ids", default=DEFAULTS["gpu_ids"])
    parser.add_argument("--scheduler", default=DEFAULTS["scheduler"], choices=["auto", "none", "cosine", "step"])
    parser.add_argument("--min-lr", type=float, default=DEFAULTS["min_lr"])
    parser.add_argument("--grad-clip", type=float, default=DEFAULTS["grad_clip"])
    parser.add_argument("--weight-decay", type=float, default=0.0, help="Weight decay for the AdamW path (0 = plain Adam).")
    parser.add_argument("--selection-metric", default=DEFAULTS["selection_metric"], choices=["mae", "f_measure", "max_f_measure"])
    parser.add_argument("--output-dir", default=DEFAULTS["output_dir"])
    parser.add_argument("--pretrained", action="store_true")
    parser.add_argument("--augment-mode", default=DEFAULTS["augment_mode"], choices=["basic", "full"])
    parser.add_argument("--zoom-vis-every", type=int, default=0)
    parser.add_argument("--zoom-vis-count", type=int, default=0)
    parser.add_argument("--train-subset", type=int, default=0,
                        help="If >0, deterministically subsample the train split to N images "
                             "(data-efficiency study). The subset is fixed by --train-subset-seed, "
                             "so it stays identical across training --seed values.")
    parser.add_argument("--train-subset-seed", type=int, default=1234,
                        help="RNG seed for choosing the train subset (independent of --seed).")
    # C3Net-R18 (Contrast-Context-Cue) module flags.
    parser.add_argument("--disable-c3net-context", action="store_true", help="Disable the PPM global-context module.")
    parser.add_argument("--disable-c3net-edge", action="store_true", help="Disable the edge cue branch and its loss.")
    parser.add_argument("--disable-c3net-deepsup", action="store_true", help="Disable multi-level deep supervision.")
    parser.add_argument("--disable-c3net-cscm", action="store_true", help="Disable the Center-Surround Contrast Modulation module.")
    parser.add_argument("--c3net-cscm-scales", default="3,7,11", help="Comma-separated surround radii for CSCM, e.g. '3,7,11' or '7'.")
    parser.add_argument("--c3net-cscm-gating", default="residual", choices=["residual", "pure"], help="CSCM gating: residual f*(1+A) or pure f*A.")
    parser.add_argument("--c3net-cscm-variant", default="diff", choices=["diff", "norm"], help="CSCM contrast: diff (f-mu) or norm (local contrast normalization).")
    parser.add_argument("--c3net-cscm-mode", default="gate", choices=["gate", "inject"], help="CSCM mode: gate (attention) or inject (residual contrast feature).")
    parser.add_argument("--c3net-cscm-gamma", type=float, default=1.0, help="CSCM modulation strength.")
    parser.add_argument("--c3net-cscm-gate", default="none", choices=["none", "uncertainty", "edge"], help="Gate contrast by coarse-prediction uncertainty (UG-CSCM) or image edges (M4).")
    parser.add_argument("--c3net-cscm-fixed", action="store_true", help="M5/V2: parameter-free fixed contrast gate (isolate prior from learned capacity).")
    parser.add_argument("--c3net-cscm-sup-weight", type=float, default=0.0, help="M2: supervise CSCM attention toward Sobel(GT) contrast.")
    parser.add_argument("--c3net-cscm-skip", action="store_true", help="M1: also apply CSCM to encoder skip features c1,c2,c3.")
    parser.add_argument("--c3net-cscm-d3", action="store_true", help="M1: also apply CSCM at the d3 (s16) decoder stage.")
    parser.add_argument("--c3net-cscm-learn-surround", action="store_true", help="M3: learnable depthwise surround instead of fixed average pool.")
    parser.add_argument("--c3net-coarse-weight", type=float, default=0.4, help="Loss weight for the coarse uncertainty head (UG-CSCM).")
    parser.add_argument("--c3net-loss", default="structure", choices=["bce", "structure", "hybrid"], help="Pixel loss for main and side outputs.")
    parser.add_argument("--c3net-edge-weight", type=float, default=0.3)
    parser.add_argument("--c3net-side-weight", type=float, default=0.4)
    parser.add_argument("--c3net-use-body-detail", action="store_true", help="Enable LDF-lite body/detail decoupled supervision.")
    parser.add_argument("--c3net-detail-kernel", type=int, default=9)
    parser.add_argument("--c3net-body-weight", type=float, default=0.4)
    parser.add_argument("--c3net-detail-weight", type=float, default=0.4)
    parser.add_argument("--c3net-freq-weight", type=float, default=0.0, help="Frequency-perception loss weight (FFT magnitude spectrum match).")
    # F3Net-R18 flags.
    parser.add_argument("--f3net-variant", default="base", choices=["base", "enhanced"])
    parser.add_argument("--f3net-loss-profile", default="base", choices=["base", "enhanced"])
    # SINet-R18 flags.
    parser.add_argument("--sinet-channel", type=int, default=32)
    # CTD-lite-R18 (Complementary Trilateral Decoder) flags.
    parser.add_argument("--ctdnet-channels", type=int, default=64)
    parser.add_argument("--disable-ctdnet-semantic", action="store_true", help="Disable the semantic path (SAP global context + CAM).")
    parser.add_argument("--disable-ctdnet-boundary", action="store_true", help="Disable the boundary path + BRM.")
    parser.add_argument("--disable-ctdnet-cam", action="store_true", help="Use plain fusion instead of the Cross Aggregation Module.")
    parser.add_argument("--ctdnet-use-cscm", action="store_true", help="Fusion: add C3Net CSCM contrast modulation to the spatial path.")
    parser.add_argument("--ctdnet-loss", default="structure", choices=["bce", "structure", "hybrid"])
    parser.add_argument("--ctdnet-side-weight", type=float, default=0.4)
    parser.add_argument("--ctdnet-edge-weight", type=float, default=0.3)
    return parser


def apply_model_defaults(args):
    if args.model == "resnet18" and args.output_dir == DEFAULTS["output_dir"]:
        args.output_dir = "runs/resnet18"
    elif args.model == "c3net_r18" and args.output_dir == DEFAULTS["output_dir"]:
        args.output_dir = "runs/c3net_r18"
    elif args.model == "ctdnet_r18" and args.output_dir == DEFAULTS["output_dir"]:
        args.output_dir = "runs/ctdnet_r18"
    elif args.model == "egnet_r18" and args.output_dir == DEFAULTS["output_dir"]:
        args.output_dir = "runs/egnet_r18"
    elif args.model == "pfa_r18":
        if args.output_dir == DEFAULTS["output_dir"]:
            args.output_dir = "runs/pfa_r18"
        if args.lr == DEFAULTS["lr"]:
            args.lr = 3e-4
    elif args.model == "poolnet_r18" and args.output_dir == DEFAULTS["output_dir"]:
        args.output_dir = "runs/poolnet_r18"
    elif args.model == "sinet_r18":
        if args.output_dir == DEFAULTS["output_dir"]:
            args.output_dir = "runs/sinet_r18"
        if args.lr == DEFAULTS["lr"]:
            args.lr = 1e-4
    elif args.model == "dss_r18":
        if args.output_dir == DEFAULTS["output_dir"]:
            args.output_dir = "runs/dss_r18"
        if args.lr == DEFAULTS["lr"]:
            args.lr = 1e-3
    elif args.model == "f3net_r18" and args.output_dir == DEFAULTS["output_dir"]:
        args.output_dir = "runs/f3net_r18"
    return args


def resolve_model_kwargs(args):
    kwargs = {"pretrained": args.pretrained}
    if args.model == "sinet_r18":
        kwargs.update(channel=args.sinet_channel)
    elif args.model == "f3net_r18":
        kwargs.update(variant=args.f3net_variant, loss_profile=args.f3net_loss_profile)
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
            freq_loss_weight=args.c3net_freq_weight,
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


def build_optimizer(model, args):
    if args.model in ("f3net_r18", "dss_r18", "egfnet_r18", "dcfnet_sl_r18"):
        return torch.optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, weight_decay=5e-4, nesterov=True)
    if args.model == "pfa_r18":
        return torch.optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, weight_decay=0.0, nesterov=True)
    # AdamW with weight_decay=0 is identical to Adam, so this stays backward compatible.
    return torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)


def build_scheduler(optimizer, args):
    if args.scheduler == "none":
        return None
    scheduler_name = "cosine" if args.scheduler == "auto" else args.scheduler
    if scheduler_name == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(args.epochs, 1), eta_min=args.min_lr)
    if scheduler_name == "step":
        step_size = max(args.epochs // 3, 1)
        return torch.optim.lr_scheduler.StepLR(optimizer, step_size=step_size, gamma=0.1)
    return None


def build_loader(dataset, batch_size, shuffle, num_workers):
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle,
                      num_workers=num_workers, pin_memory=True,
                      prefetch_factor=4 if num_workers > 0 else None,
                      persistent_workers=True if num_workers > 0 else False)


@torch.no_grad()
def maybe_save_zoom_visuals(model, loader, device, output_dir, epoch, max_samples):
    if max_samples <= 0:
        return

    model.to(device)
    was_training = model.training
    model.eval()
    images, masks, names = next(iter(loader))
    images = images.to(device)
    masks = masks.to(device)
    outputs = model(images)
    if not isinstance(outputs, dict) or "boxes" not in outputs:
        if was_training:
            model.train()
        return

    probs = torch.sigmoid(outputs["pred"])
    coarse_probs = torch.sigmoid(outputs["coarse"])
    uncertainty = outputs["uncertainty"]
    boxes = outputs["boxes"].detach().cpu()
    vis_dir = Path(output_dir) / "visuals" / f"epoch_{epoch:03d}"

    for index in range(min(max_samples, images.shape[0])):
        patch_offset = index * boxes.shape[1]
        if "delta" in outputs:
            vis_tensor = outputs["delta"][patch_offset : patch_offset + 1]
        elif "refined_patch" in outputs:
            vis_tensor = outputs["refined_patch"][patch_offset : patch_offset + 1]
        else:
            continue
        save_zoom_visualization(
            images[index].detach().cpu(),
            masks[index].detach().cpu(),
            uncertainty[index].detach().cpu(),
            coarse_probs[index].detach().cpu(),
            probs[index].detach().cpu(),
            F.interpolate(vis_tensor, size=images.shape[-2:], mode="bilinear", align_corners=False)[0].detach().cpu(),
            boxes[index].tolist(),
            vis_dir / f"{names[index]}.png",
        )

    if was_training:
        model.train()


def main():
    args = apply_model_defaults(build_parser().parse_args())
    set_seed(args.seed)
    runtime_device = resolve_runtime_device(args.device, args.gpu_ids)

    train_dataset = ECSSDDataset(
        args.data_root,
        split="train",
        image_size=args.image_size,
        augment=True,
        split_file=args.split_file,
        augment_mode=args.augment_mode,
    )
    val_dataset = ECSSDDataset(
        args.data_root,
        split="val",
        image_size=args.image_size,
        augment=False,
        split_file=args.split_file,
        augment_mode=args.augment_mode,
    )
    if args.train_subset and 0 < args.train_subset < len(train_dataset):
        import random as _random
        from torch.utils.data import Subset
        rng = _random.Random(args.train_subset_seed)
        indices = sorted(rng.sample(range(len(train_dataset)), args.train_subset))
        train_dataset = Subset(train_dataset, indices)
        print(f"[train-subset] using {len(train_dataset)} of train images "
              f"(subset-seed={args.train_subset_seed})")

    train_loader = build_loader(train_dataset, args.batch_size, True, args.num_workers)
    val_loader = build_loader(val_dataset, args.batch_size, False, args.num_workers)

    model = build_model(args.model, **resolve_model_kwargs(args))
    model = model.to(runtime_device)
    model, used_gpu_ids = maybe_wrap_data_parallel(model, args.device, args.gpu_ids)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = build_optimizer(model, args)
    scheduler = build_scheduler(optimizer, args)

    maximize_metrics = {"f_measure", "max_f_measure"}
    best_metric = float("-inf") if args.selection_metric in maximize_metrics else float("inf")
    best_epoch = 0
    output_dir = Path(args.output_dir)
    history = TrainingHistory(output_dir)
    save_json(vars(args), output_dir / "config.json")

    for epoch in range(1, args.epochs + 1):
        start_time = time.time()
        train_loss = train_one_epoch(model, train_loader, criterion, optimizer, device=runtime_device, grad_clip=args.grad_clip)
        metrics = evaluate(model, val_loader, device=runtime_device)
        epoch_seconds = time.time() - start_time
        current_lr = optimizer.param_groups[0]["lr"]

        print(
            f"epoch={epoch} train_loss={train_loss:.4f} "
            f"val_mae={metrics['mae']:.4f} "
            f"val_f_measure@0.5={metrics['f_measure']:.4f} "
            f"val_max_f_measure={metrics['max_f_measure']:.4f} "
            f"val_max_f_threshold={metrics['max_f_threshold']:.4f} "
            f"val_s_measure={metrics['s_measure']:.4f} "
            f"val_e_measure={metrics['e_measure']:.4f} "
            f"val_pixel_acc={metrics['pixel_acc']:.4f} val_iou={metrics['iou']:.4f} "
            f"lr={current_lr:.6f} epoch_time={epoch_seconds:.2f}s "
            f"device={runtime_device} gpu_ids={used_gpu_ids if used_gpu_ids else 'none'}"
        )
        if "coarse_max_f_measure" in metrics:
            print(
                f"val_coarse_max_f_measure={metrics['coarse_max_f_measure']:.4f} "
                f"val_delta_max_f={metrics['delta_max_f']:.4f} "
                f"val_delta_iou={metrics['delta_iou']:.4f}"
            )
        if "patch_delta_abs_mean" in metrics:
            print(
                f"val_patch_coarse_mae={metrics['patch_coarse_mae']:.4f} "
                f"val_patch_refined_mae={metrics['patch_refined_mae']:.4f} "
                f"val_patch_delta_mae={metrics['patch_delta_mae']:.4f} "
                f"val_patch_delta_abs_mean={metrics['patch_delta_abs_mean']:.4f} "
                f"val_patch_delta_abs_max={metrics['patch_delta_abs_max']:.4f}"
            )

        selected_value = metrics[args.selection_metric]
        is_best = selected_value > best_metric if args.selection_metric in maximize_metrics else selected_value < best_metric
        if is_best:
            best_metric = selected_value
            best_epoch = epoch
            save_checkpoint(
                {
                    "model": unwrap_model(model).state_dict(),
                    "epoch": epoch,
                    "metrics": metrics,
                    "args": vars(args),
                },
                output_dir / "best.pt",
            )

        history.append(
            epoch=epoch,
            train_loss=round(train_loss, 6),
            val_mae=round(metrics["mae"], 6),
            val_f_measure=round(metrics["f_measure"], 6),
            val_max_f_measure=round(metrics["max_f_measure"], 6),
            val_max_f_threshold=round(metrics["max_f_threshold"], 6),
            val_pixel_acc=round(metrics["pixel_acc"], 6),
            val_iou=round(metrics["iou"], 6),
            lr=round(current_lr, 8),
            epoch_seconds=round(epoch_seconds, 3),
            selection_metric=args.selection_metric,
            selected_value=round(selected_value, 6),
            is_best=is_best,
            best_epoch=best_epoch,
            coarse_mae=round(metrics["coarse_mae"], 6) if "coarse_mae" in metrics else None,
            coarse_f_measure=round(metrics["coarse_f_measure"], 6) if "coarse_f_measure" in metrics else None,
            coarse_max_f_measure=round(metrics["coarse_max_f_measure"], 6) if "coarse_max_f_measure" in metrics else None,
            coarse_max_f_threshold=round(metrics["coarse_max_f_threshold"], 6) if "coarse_max_f_threshold" in metrics else None,
            coarse_pixel_acc=round(metrics["coarse_pixel_acc"], 6) if "coarse_pixel_acc" in metrics else None,
            coarse_iou=round(metrics["coarse_iou"], 6) if "coarse_iou" in metrics else None,
            delta_mae=round(metrics["delta_mae"], 6) if "delta_mae" in metrics else None,
            delta_max_f=round(metrics["delta_max_f"], 6) if "delta_max_f" in metrics else None,
            delta_iou=round(metrics["delta_iou"], 6) if "delta_iou" in metrics else None,
            patch_coarse_mae=round(metrics["patch_coarse_mae"], 6) if "patch_coarse_mae" in metrics else None,
            patch_refined_mae=round(metrics["patch_refined_mae"], 6) if "patch_refined_mae" in metrics else None,
            patch_delta_mae=round(metrics["patch_delta_mae"], 6) if "patch_delta_mae" in metrics else None,
            patch_coarse_iou=round(metrics["patch_coarse_iou"], 6) if "patch_coarse_iou" in metrics else None,
            patch_refined_iou=round(metrics["patch_refined_iou"], 6) if "patch_refined_iou" in metrics else None,
            patch_delta_iou=round(metrics["patch_delta_iou"], 6) if "patch_delta_iou" in metrics else None,
            patch_delta_abs_mean=round(metrics["patch_delta_abs_mean"], 6) if "patch_delta_abs_mean" in metrics else None,
            patch_delta_abs_max=round(metrics["patch_delta_abs_max"], 6) if "patch_delta_abs_max" in metrics else None,
        )
        history.save()

        if args.zoom_vis_every > 0 and epoch % args.zoom_vis_every == 0:
            maybe_save_zoom_visuals(model, val_loader, runtime_device, output_dir, epoch, args.zoom_vis_count)

        save_checkpoint(
            {
                "model": unwrap_model(model).state_dict(),
                "epoch": epoch,
                "metrics": metrics,
                "args": vars(args),
            },
            output_dir / "last.pt",
        )

        if scheduler is not None:
            scheduler.step()


if __name__ == "__main__":
    main()
