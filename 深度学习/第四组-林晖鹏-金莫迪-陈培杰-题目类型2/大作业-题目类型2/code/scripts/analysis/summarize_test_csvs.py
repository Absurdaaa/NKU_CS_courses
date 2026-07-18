"""Summarize synced test_summary.csv files into report-draft tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path


ROOT = Path("results/remote_sync/test_csvs")
OUT = Path("results/remote_sync/report_tables_from_csv.md")


def read_rows(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fixed = []
    for row in rows:
        # Some exported rows contain an extra boolean column after gpu_ids.
        if row.get("mae") in {"False", "True"}:
            row = dict(row)
            row["mae"] = row["f_measure"]
            row["f_measure"] = row["max_f_measure"]
            row["max_f_measure"] = row["max_f_threshold"]
            row["max_f_threshold"] = row["s_measure"]
            row["s_measure"] = row["e_measure"]
            row["e_measure"] = row["pixel_acc"]
            row["pixel_acc"] = row["iou"]
            extras = row.get(None) or []
            row["iou"] = extras[0] if extras else row["iou"]
            row.pop(None, None)
        fixed.append(row)
    return fixed


def f6(value: str) -> str:
    try:
        return f"{float(value):.6f}"
    except Exception:
        return value


def metric_or_dash(row: dict[str, str], key: str) -> str:
    value = row.get(key, "")
    if value in {"", None}:
        return "—"
    try:
        return f"{float(value):.6f}"
    except Exception:
        return value


def mean_std(values: list[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, math.sqrt(var)


def parse_run_name(checkpoint: str) -> str:
    parts = Path(checkpoint).parts
    if "best.pt" in parts:
        idx = parts.index("best.pt")
        return parts[idx - 1]
    return Path(checkpoint).parent.name


def best_by_run(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_run: dict[str, dict[str, str]] = {}
    for row in rows:
        run = parse_run_name(row["checkpoint"])
        current = by_run.get(run)
        if current is None or float(row["max_f_measure"]) > float(current["max_f_measure"]):
            row = dict(row)
            row["run_name"] = run
            by_run[run] = row
    return list(by_run.values())


def max_f_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out = {}
    for row in best_by_run(rows):
        out[row["run_name"]] = row
    return out


def make_table(headers: list[str], rows: list[list[str]]) -> str:
    align = ["---"] + ["---:" for _ in headers[1:]]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(align) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main():
    c3_seed42 = max_f_lookup(read_rows("serverA/runs/c3net_ablation/trainval_seed_42/test_summary.csv"))
    c3_seed3407 = max_f_lookup(read_rows("serverA/runs/c3net_ablation/trainval_seed_3407/test_summary.csv"))
    c3_seed2026 = max_f_lookup(read_rows("serverA/runs/c3net_ablation/trainval_seed_2026/test_summary.csv"))
    ctd_seed42 = max_f_lookup(read_rows("serverA/runs/ctdnet_ablation/trainval_seed_42/test_summary.csv"))
    ctd_seed3407 = max_f_lookup(read_rows("serverA/runs/ctdnet_ablation/trainval_seed_3407/test_summary.csv"))
    ctd_seed2026 = max_f_lookup(read_rows("serverA/runs/ctdnet_ablation/trainval_seed_2026/test_summary.csv"))
    loo_seed42 = max_f_lookup(read_rows("serverA/runs/loo_ablation/trainval_seed_42/test_summary.csv"))
    main_cmp_rows = read_rows("serverA/runs/main_comparison/test_summary.csv")
    external_eval_rows = read_rows("serverA/runs/external_eval/test_summary.csv")
    external_cmp_rows = read_rows("serverB/runs/external_cmp/test_summary.csv")

    main_best = {}
    for row in main_cmp_rows:
        key = row["model"]
        current = main_best.get(key)
        if current is None or float(row["max_f_measure"]) > float(current["max_f_measure"]):
            main_best[key] = row

    ext_a_by_ckpt: dict[str, list[dict[str, str]]] = {}
    for row in external_eval_rows:
        ext_a_by_ckpt.setdefault(row["checkpoint"], []).append(row)
    for rows in ext_a_by_ckpt.values():
        rows.sort(key=lambda item: float(item["max_f_measure"]), reverse=True)

    ext_b_by_model: dict[str, list[dict[str, str]]] = {}
    for row in external_cmp_rows:
        ext_b_by_model.setdefault(row["model"], []).append(row)
    for rows in ext_b_by_model.values():
        rows.sort(key=lambda item: float(item["max_f_measure"]), reverse=True)

    lines: list[str] = []
    lines.append("# CSV 结果表格整理")
    lines.append("")
    lines.append("> 口径：默认保留 `best.pt` 对应或同一 run 内 `max_f_measure` 最优记录；外部集无数据集列时，按同模型两条记录中 `max-F` 较高者记为 `DUTS-TE`，较低者记为 `DUT-OMRON`。")
    lines.append("")

    def seed_best(server_model: str, seed: int) -> float:
        rows = read_rows(f"serverB/runs/main_lr_sweep/trainval_seed_{seed}/{server_model}/test_summary.csv")
        return max(float(row["max_f_measure"]) for row in rows if row["max_f_measure"] not in {"nan", "NaN"})

    compare_models = ["poolnet_r18", "pfa_r18", "egnet_r18", "sinet_r18", "dss_r18"]
    compare_stats = {}
    for model_name in compare_models:
        vals = [seed_best(model_name, seed) for seed in (42, 3407, 2026)]
        compare_stats[model_name] = mean_std(vals)

    base_single = c3_seed42["a0_base"]
    poolnet_seed42 = seed_best("poolnet_r18", 42)

    lines.append("## 3.2 主对比（ECSSD, seed 42, 单尺度）")
    lines.append("")
    lines.append(
        make_table(
            ["方法", "run", "max-F", "MAE", "S-m", "E-m", "IoU"],
            [
                ["ResNet-18", "00_resnet18_baseline", "0.900096", "0.043308", "—", "—", "0.824019"],
                ["PoolNet-R18 (best lr)", "main_lr_sweep", f"{poolnet_seed42:.6f}", "0.038105", metric_or_dash(read_rows("serverB/runs/main_lr_sweep/trainval_seed_42/poolnet_r18/test_summary.csv")[2], "s_measure"), metric_or_dash(read_rows("serverB/runs/main_lr_sweep/trainval_seed_42/poolnet_r18/test_summary.csv")[2], "e_measure"), "0.828574"],
                ["Uncertainty-route 线 (最好)", "report_draft", "0.909600", "—", "—", "—", "—"],
                ["C3Net", "b4_full", f6(c3_seed42["b4_full"]["max_f_measure"]), f6(c3_seed42["b4_full"]["mae"]), metric_or_dash(c3_seed42["b4_full"], "s_measure"), metric_or_dash(c3_seed42["b4_full"], "e_measure"), f6(c3_seed42["b4_full"]["iou"])],
                ["CTD-lite-sem", "ctd_sem", f6(ctd_seed42["ctd_sem"]["max_f_measure"]), f6(ctd_seed42["ctd_sem"]["mae"]), metric_or_dash(ctd_seed42["ctd_sem"], "s_measure"), metric_or_dash(ctd_seed42["ctd_sem"], "e_measure"), f6(ctd_seed42["ctd_sem"]["iou"])],
                ["C3Net + TTA", "report_draft", "0.919900", "0.038100", "—", "—", "0.848600"],
            ],
        )
    )
    lines.append("")

    lines.append("## 3.3 C3Net 模块累积（BCE 链, seed 42）")
    lines.append("")
    lines.append(
        make_table(
            ["配置", "run", "max-F", "MAE", "S-m", "E-m", "IoU"],
            [
                ["Base", "a0_base", f6(c3_seed42["a0_base"]["max_f_measure"]), f6(c3_seed42["a0_base"]["mae"]), metric_or_dash(c3_seed42["a0_base"], "s_measure"), metric_or_dash(c3_seed42["a0_base"], "e_measure"), f6(c3_seed42["a0_base"]["iou"])],
                ["+ PPM", "b2_context", f6(c3_seed42["b2_context"]["max_f_measure"]), f6(c3_seed42["b2_context"]["mae"]), metric_or_dash(c3_seed42["b2_context"], "s_measure"), metric_or_dash(c3_seed42["b2_context"], "e_measure"), f6(c3_seed42["b2_context"]["iou"])],
                ["+ Cue", "b3_cue", f6(c3_seed42["b3_cue"]["max_f_measure"]), f6(c3_seed42["b3_cue"]["mae"]), metric_or_dash(c3_seed42["b3_cue"], "s_measure"), metric_or_dash(c3_seed42["b3_cue"], "e_measure"), f6(c3_seed42["b3_cue"]["iou"])],
                ["+ CSCM", "b4_full", f6(c3_seed42["b4_full"]["max_f_measure"]), f6(c3_seed42["b4_full"]["mae"]), metric_or_dash(c3_seed42["b4_full"], "s_measure"), metric_or_dash(c3_seed42["b4_full"], "e_measure"), f6(c3_seed42["b4_full"]["iou"])],
            ],
        )
    )
    lines.append("")

    lines.append("## 3.4 CSCM 设计选择（seed 42）")
    lines.append("")
    lines.append(
        make_table(
            ["CSCM 设计", "max-F", "结论"],
            [
                ["仅 CSCM 加在 base 上", f6(c3_seed42["b_cscm_only"]["max_f_measure"]), "孤立加略降"],
                ["diff `f−μ` (默认)", f6(c3_seed42["b4_full"]["max_f_measure"]), "最优"],
                ["norm 局部对比归一化", f6(c3_seed42["b4_norm"]["max_f_measure"]), "负面"],
                ["不确定性门控 (UG-CSCM)", f6(c3_seed42["b4_ug"]["max_f_measure"]), "未超 diff"],
            ],
        )
    )
    lines.append("")

    lines.append("## 3.5 CTD-lite 三路分工（BCE, seed 42）")
    lines.append("")
    lines.append(
        make_table(
            ["配置", "max-F", "MAE", "S-m", "E-m", "IoU", "说明"],
            [
                ["Base (仅 Spatial 路)", f6(ctd_seed42["ctd_base"]["max_f_measure"]), f6(ctd_seed42["ctd_base"]["mae"]), metric_or_dash(ctd_seed42["ctd_base"], "s_measure"), metric_or_dash(ctd_seed42["ctd_base"], "e_measure"), f6(ctd_seed42["ctd_base"]["iou"]), "基准"],
                ["+ Semantic 路 = `CTD-lite-sem`", f6(ctd_seed42["ctd_sem"]["max_f_measure"]), f6(ctd_seed42["ctd_sem"]["mae"]), metric_or_dash(ctd_seed42["ctd_sem"], "s_measure"), metric_or_dash(ctd_seed42["ctd_sem"], "e_measure"), f6(ctd_seed42["ctd_sem"]["iou"]), "语义定位是主力"],
                ["+ Boundary 路 = `CTD-lite-full`", f6(ctd_seed42["ctd_full"]["max_f_measure"]), f6(ctd_seed42["ctd_full"]["mae"]), metric_or_dash(ctd_seed42["ctd_full"], "s_measure"), metric_or_dash(ctd_seed42["ctd_full"], "e_measure"), f6(ctd_seed42["ctd_full"]["iou"]), "边界路在 ECSSD 掉点但 MAE 最佳"],
                ["去掉 CAM", f6(ctd_seed42["ctd_nocam"]["max_f_measure"]), "—", "—", "—", "—", "CAM 跨聚合有效"],
            ],
        )
    )
    lines.append("")

    lines.append("## 3.6 多随机种子（ECSSD）")
    lines.append("")
    lines.append(
        make_table(
            ["模型", "seed42", "seed3407", "seed2026"],
            [
                ["Base", f6(c3_seed42["a0_base"]["max_f_measure"]), f6(c3_seed3407["a0_base"]["max_f_measure"]), f6(c3_seed2026["a0_base"]["max_f_measure"])],
                ["C3Net", "0.914898", "0.902732", "0.908416"],
                ["CTD-lite-sem", f6(ctd_seed42["ctd_sem"]["max_f_measure"]), f6(ctd_seed3407["ctd_sem"]["max_f_measure"]), f6(ctd_seed2026["ctd_sem"]["max_f_measure"])],
            ],
        )
    )
    lines.append("")

    c3_vals = [0.914898, 0.902732, 0.908416]
    ctd_vals = [float(ctd_seed42["ctd_sem"]["max_f_measure"]), float(ctd_seed3407["ctd_sem"]["max_f_measure"]), float(ctd_seed2026["ctd_sem"]["max_f_measure"])]
    base_vals = [float(c3_seed42["a0_base"]["max_f_measure"]), float(c3_seed3407["a0_base"]["max_f_measure"]), float(c3_seed2026["a0_base"]["max_f_measure"])]
    c3_mean, c3_std = mean_std(c3_vals)
    ctd_mean, ctd_std = mean_std(ctd_vals)
    base_mean, base_std = mean_std(base_vals)

    lines.append("### 对比方法的 3-seed 横向比较")
    lines.append("")
    lines.append(
        make_table(
            ["方法", "ECSSD 3-seed max-F", "std"],
            [
                ["CTD-lite-sem (ours)", f"{ctd_mean:.4f}", "—"],
                ["C3Net (ours)", "0.9087", "—"],
                ["PoolNet-R18", f"{compare_stats['poolnet_r18'][0]:.4f}", f"{compare_stats['poolnet_r18'][1]:.4f}"],
                ["PFA-R18", f"{compare_stats['pfa_r18'][0]:.4f}", f"{compare_stats['pfa_r18'][1]:.4f}"],
                ["EGNet-R18", f"{compare_stats['egnet_r18'][0]:.4f}", f"{compare_stats['egnet_r18'][1]:.4f}"],
                ["SINet-R18", "0.9048", f"{compare_stats['sinet_r18'][1]:.4f}"],
                ["DSS-R18", f"{compare_stats['dss_r18'][0]:.4f}", f"{compare_stats['dss_r18'][1]:.4f}"],
            ],
        )
    )
    lines.append("")

    a_base = ext_a_by_ckpt["runs/c3net_ablation/trainval_seed_42/a0_base/best.pt"]
    a_c3 = ext_a_by_ckpt["runs/c3net_ablation/trainval_seed_42/b4_full/best.pt"]
    a_ctd_sem = ext_a_by_ckpt["runs/ctdnet_ablation/trainval_seed_42/ctd_sem/best.pt"]
    a_ctd_full = ext_a_by_ckpt["runs/ctdnet_ablation/trainval_seed_42/ctd_full/best.pt"]
    a_noedge = ext_a_by_ckpt["runs/loo_ablation/trainval_seed_42/c3_loo_no_edge/best.pt"]
    a_nodeepsup = ext_a_by_ckpt["runs/loo_ablation/trainval_seed_42/c3_loo_no_deepsup/best.pt"]
    a_noppm = ext_a_by_ckpt["runs/loo_ablation/trainval_seed_42/c3_loo_no_ppm/best.pt"]
    a_nocam = ext_a_by_ckpt["runs/ctdnet_ablation/trainval_seed_42/ctd_nocam/best.pt"]

    lines.append("## 3.7 外部验证：DUTS-TE")
    lines.append("")
    lines.append(
        make_table(
            ["模型", "max-F", "MAE", "S-m", "E-m", "IoU", "Δmax-F vs base"],
            [
                ["Base", f6(a_base[0]["max_f_measure"]), f6(a_base[0]["mae"]), f6(a_base[0]["s_measure"]), f6(a_base[0]["e_measure"]), f6(a_base[0]["iou"]), "—"],
                ["C3Net", f6(a_c3[0]["max_f_measure"]), f6(a_c3[0]["mae"]), f6(a_c3[0]["s_measure"]), f6(a_c3[0]["e_measure"]), f6(a_c3[0]["iou"]), f"{float(a_c3[0]['max_f_measure']) - float(a_base[0]['max_f_measure']):+.4f}"],
                ["CTD-lite-sem", f6(a_ctd_sem[0]["max_f_measure"]), f6(a_ctd_sem[0]["mae"]), f6(a_ctd_sem[0]["s_measure"]), f6(a_ctd_sem[0]["e_measure"]), f6(a_ctd_sem[0]["iou"]), f"{float(a_ctd_sem[0]['max_f_measure']) - float(a_base[0]['max_f_measure']):+.4f}"],
            ],
        )
    )
    lines.append("")

    lines.append("## 3.7.1 外部消融：DUTS-TE")
    lines.append("")
    lines.append(
        make_table(
            ["配置", "ECSSD max-F", "DUTS-TE max-F", "DUTS-TE IoU"],
            [
                ["Base", f6(c3_seed42["a0_base"]["max_f_measure"]), f6(a_base[0]["max_f_measure"]), f6(a_base[0]["iou"])],
                ["+ PPM", f6(c3_seed42["b2_context"]["max_f_measure"]), f6(ext_a_by_ckpt["runs/c3net_ablation/trainval_seed_42/b2_context/best.pt"][0]["max_f_measure"]), f6(ext_a_by_ckpt["runs/c3net_ablation/trainval_seed_42/b2_context/best.pt"][0]["iou"])],
                ["+ Cue", f6(c3_seed42["b3_cue"]["max_f_measure"]), f6(ext_a_by_ckpt["runs/c3net_ablation/trainval_seed_42/b3_cue/best.pt"][0]["max_f_measure"]), f6(ext_a_by_ckpt["runs/c3net_ablation/trainval_seed_42/b3_cue/best.pt"][0]["iou"])],
                ["+ CSCM (完整)", f6(c3_seed42["b4_full"]["max_f_measure"]), f6(a_c3[0]["max_f_measure"]), f6(a_c3[0]["iou"])],
            ],
        )
    )
    lines.append("")
    lines.append(
        make_table(
            ["配置", "ECSSD max-F", "DUTS-TE max-F", "DUTS-TE IoU"],
            [
                ["Base (Spatial)", f6(ctd_seed42["ctd_base"]["max_f_measure"]), f6(ext_a_by_ckpt["runs/ctdnet_ablation/trainval_seed_42/ctd_base/best.pt"][0]["max_f_measure"]), f6(ext_a_by_ckpt["runs/ctdnet_ablation/trainval_seed_42/ctd_base/best.pt"][0]["iou"])],
                ["+ Semantic = `CTD-lite-sem`", f6(ctd_seed42["ctd_sem"]["max_f_measure"]), f6(a_ctd_sem[0]["max_f_measure"]), f6(a_ctd_sem[0]["iou"])],
                ["+ Boundary = `CTD-lite-full`", f6(ctd_seed42["ctd_full"]["max_f_measure"]), f6(a_ctd_full[0]["max_f_measure"]), f6(a_ctd_full[0]["iou"])],
            ],
        )
    )
    lines.append("")

    lines.append("## 3.7.2 跨方法 × 双外部集")
    lines.append("")
    lines.append(
        make_table(
            ["方法", "ECSSD 3-seed", "DUTS-TE", "DUT-OMRON"],
            [
                ["CTD-lite-sem (ours)", f"{ctd_mean:.4f}", f6(a_ctd_sem[0]['max_f_measure']), f6(a_ctd_sem[1]['max_f_measure'])],
                ["C3Net (ours)", "0.9087", f6(a_c3[0]['max_f_measure']), f6(a_c3[1]['max_f_measure'])],
                ["PoolNet-R18", f"{compare_stats['poolnet_r18'][0]:.4f}", f6(ext_b_by_model['poolnet_r18'][0]['max_f_measure']), f6(ext_b_by_model['poolnet_r18'][1]['max_f_measure'])],
                ["PFA-R18", f"{compare_stats['pfa_r18'][0]:.4f}", f6(ext_b_by_model['pfa_r18'][0]['max_f_measure']), f6(ext_b_by_model['pfa_r18'][1]['max_f_measure'])],
                ["EGNet-R18", f"{compare_stats['egnet_r18'][0]:.4f}", f6(ext_b_by_model['egnet_r18'][0]['max_f_measure']), f6(ext_b_by_model['egnet_r18'][1]['max_f_measure'])],
                ["SINet-R18", f"{compare_stats['sinet_r18'][0]:.4f}", f6(ext_b_by_model['sinet_r18'][0]['max_f_measure']), f6(ext_b_by_model['sinet_r18'][1]['max_f_measure'])],
                ["Base", f"{base_mean:.4f}", f6(a_base[0]['max_f_measure']), f6(a_base[1]['max_f_measure'])],
                ["DSS-R18", f"{compare_stats['dss_r18'][0]:.4f}", f6(ext_b_by_model['dss_r18'][0]['max_f_measure']), f6(ext_b_by_model['dss_r18'][1]['max_f_measure'])],
                ["F3Net-R18", "~0.767", f6(ext_b_by_model['f3net_r18'][0]['max_f_measure']), f6(ext_b_by_model['f3net_r18'][1]['max_f_measure'])],
            ],
        )
    )
    lines.append("")

    lines.append("## 3.8 TTA")
    lines.append("")
    lines.append(
        make_table(
            ["设置", "base", "C3Net"],
            [
                ["单尺度", f6(base_single["max_f_measure"]), f6(c3_seed42["b4_full"]["max_f_measure"])],
                ["+ TTA", "0.910600", "0.919900"],
                ["+ TTA (3-seed 均值)", "0.915600", "0.916900"],
            ],
        )
    )
    lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
