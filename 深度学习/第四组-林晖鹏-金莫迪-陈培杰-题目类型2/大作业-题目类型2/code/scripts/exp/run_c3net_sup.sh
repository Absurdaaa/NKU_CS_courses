#!/usr/bin/env bash
# C3Net supervision-line experiments (the reliable lever on small SOD data):
# Hybrid loss (BCE+IoU+SSIM) + LDF-lite body/detail decoupled supervision.
#   ./run_c3net_sup.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"
DATA_ROOT="data/ECSSD"; ROOT="runs/c3net_ablation"; SPLIT="splits/trainval_seed_42.json"
IMG=352; BS=16; LR=3e-4; PY="${PY:-python}"
split_name="$(basename "${SPLIT}" .json)"

# job = "tag|epochs|augmode|flags"
JOBS=(
  "s_hybrid|200|basic|--c3net-loss hybrid"
  "s_bd|200|basic|--c3net-loss hybrid --c3net-use-body-detail"
  "s_suponly|200|basic|--c3net-loss hybrid --c3net-use-body-detail --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "s_bd_e60|60|basic|--c3net-loss hybrid --c3net-use-body-detail"
  "s_hybrid_e60|60|basic|--c3net-loss hybrid"
  "s_suponly_e60|60|basic|--c3net-loss hybrid --c3net-use-body-detail --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r tag epochs augmode flags <<< "${job}"
  out="${ROOT}/${split_name}/${tag}"
  echo "[gpu ${GPU_ID}] === ${tag} (e${epochs}) ==="
  if [ -f "${out}/best.pt" ] && [ -f "${out}/test_metrics.json" ]; then echo "[gpu ${GPU_ID}] skip: ${tag}"; continue; fi
  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --model c3net_r18 --pretrained --split-file "${SPLIT}" \
      --image-size ${IMG} --batch-size ${BS} --epochs "${epochs}" --lr ${LR} \
      --device cuda --gpu-ids 0 --selection-metric max_f_measure --augment-mode "${augmode}" \
      --output-dir "${out}" ${flags} || { echo "[gpu ${GPU_ID}] TRAIN FAIL: ${tag}"; continue; }
  fi
  PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
    --model c3net_r18 --pretrained --split-file "${SPLIT}" --split test \
    --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
    --checkpoint "${out}/best.pt" --output-dir "${out}" ${flags} \
    || echo "[gpu ${GPU_ID}] EVAL FAIL: ${tag}"
done
echo "[gpu ${GPU_ID}] sup worker ${WORKER_INDEX} done."
