#!/usr/bin/env bash
# Leave-one-out / leave-two-out ablation: start from the FULL model and remove
# one (or two) modules to measure each module's marginal contribution.
#   ./run_loo.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"
ROOT="runs/loo_ablation"; SPLIT="splits/trainval_seed_42.json"
IMG=352; BS=16; LR=3e-4; EP=200; PY="${PY:-python}"
split_name="$(basename "${SPLIT}" .json)"

# job = "tag|model|flags"  (flags passed identically to train + eval)
JOBS=(
  # ---- C3Net leave-one-out (from full = PPM+edge+deepsup+CSCM, BCE) ----
  "c3_loo_no_ppm|c3net_r18|--c3net-loss bce --disable-c3net-context"
  "c3_loo_no_edge|c3net_r18|--c3net-loss bce --disable-c3net-edge"
  "c3_loo_no_deepsup|c3net_r18|--c3net-loss bce --disable-c3net-deepsup"
  # ---- C3Net leave-two-out ----
  "c3_no_ppm_edge|c3net_r18|--c3net-loss bce --disable-c3net-context --disable-c3net-edge"
  # ---- CTD leave-one-out (from full = semantic+spatial+boundary+CAM, BCE) ----
  "ctd_loo_no_sem|ctdnet_r18|--ctdnet-loss bce --disable-ctdnet-semantic"
  # ---- CTD leave-two-out ----
  "ctd_no_sem_cam|ctdnet_r18|--ctdnet-loss bce --disable-ctdnet-semantic --disable-ctdnet-cam"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r tag model flags <<< "${job}"
  out="${ROOT}/${split_name}/${tag}"
  echo "[gpu ${GPU_ID}] === ${tag} ==="
  if [ -f "${out}/best.pt" ] && [ -f "${out}/test_metrics.json" ]; then echo "[gpu ${GPU_ID}] skip: ${tag}"; continue; fi
  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --model "${model}" --pretrained --split-file "${SPLIT}" \
      --image-size ${IMG} --batch-size ${BS} --epochs ${EP} --lr ${LR} \
      --device cuda --gpu-ids 0 --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" ${flags} || { echo "[gpu ${GPU_ID}] TRAIN FAIL: ${tag}"; continue; }
  fi
  PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
    --model "${model}" --pretrained --split-file "${SPLIT}" --split test \
    --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
    --checkpoint "${out}/best.pt" --output-dir "${out}" ${flags} \
    || echo "[gpu ${GPU_ID}] EVAL FAIL: ${tag}"
done
echo "[gpu ${GPU_ID}] loo worker ${WORKER_INDEX} done."
