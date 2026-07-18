#!/usr/bin/env bash
# Wave-1 method enhancements vs a fresh full C3Net reference (identical protocol).
#   M1 multi-stage (skip / d3 / both), M2 contrast-supervision (0.2 / 0.5),
#   M5 fixed (parameter-free) gate.  Eval on ECSSD-300 + DUTS-TE + DUT-OMRON.
# Judge on the EXTERNAL sets (ECSSD-300 is at ceiling). Seeds 42 + 3407.
#   ./run_method_enh.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"
PY="${PY:-python}"
ROOT="runs/method_enh"
IMG=352; BS=16; EPOCHS=200; LR=3e-4
SPLITS=(splits/trainval_seed_42.json splits/trainval_seed_3407.json splits/trainval_seed_2026.json)

CFGS=(
  "full_ref|"
  "m1_skip|--c3net-cscm-skip"
  "m1_d3|--c3net-cscm-d3"
  "m1_both|--c3net-cscm-skip --c3net-cscm-d3"
  "m2_sup02|--c3net-cscm-sup-weight 0.2"
  "m2_sup05|--c3net-cscm-sup-weight 0.5"
  "m5_fixed|--c3net-cscm-fixed"
  "m3_learnsurround|--c3net-cscm-learn-surround"
  "m4_edgegate|--c3net-cscm-gate edge"
  "combo_m1m2|--c3net-cscm-skip --c3net-cscm-d3 --c3net-cscm-sup-weight 0.2"
)
EXTS=(
  "duts|data/DUTS-TE|splits/duts_te.json"
  "omron|data/DUT-OMRON|splits/dutomron.json"
)

JOBS=()
for split in "${SPLITS[@]}"; do
  for cfg in "${CFGS[@]}"; do JOBS+=("${split}|${cfg}"); done
done

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r split name flags <<< "${job}"
  sname="$(basename "${split}" .json)"
  out="${ROOT}/${sname}/${name}"
  echo "[gpu ${GPU_ID}] === ${sname}/${name} ==="

  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --model c3net_r18 --pretrained --split-file "${split}" \
      --image-size ${IMG} --batch-size ${BS} --epochs ${EPOCHS} --lr ${LR} \
      --device cuda --gpu-ids 0 --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" ${flags} \
      || { echo "[gpu ${GPU_ID}] TRAIN FAIL ${sname}/${name}"; continue; }
  fi

  if [ ! -f "${out}/test_metrics.json" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
      --model c3net_r18 --pretrained --split-file "${split}" --split test \
      --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
      --checkpoint "${out}/best.pt" --output-dir "${out}" ${flags} \
      || echo "[gpu ${GPU_ID}] EVAL FAIL ecssd ${sname}/${name}"
  fi

  for e in "${EXTS[@]}"; do
    IFS='|' read -r ds droot esplit <<< "${e}"
    if [ ! -f "${out}/${ds}/test_metrics.json" ]; then
      PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
        --model c3net_r18 --pretrained --data-root "${droot}" --split-file "${esplit}" --split test \
        --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
        --checkpoint "${out}/best.pt" --output-dir "${out}/${ds}" ${flags} \
        || echo "[gpu ${GPU_ID}] EVAL FAIL ${ds} ${sname}/${name}"
    fi
  done
done
echo "[gpu ${GPU_ID}] method-enh worker ${WORKER_INDEX} done."
