#!/usr/bin/env bash
# CTD-lite-R18 ablation sweep (trilateral decoder).
#   ./run_ctdnet.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"
DATA_ROOT="data/ECSSD"; ROOT="runs/ctdnet_ablation"; SPLIT="splits/trainval_seed_42.json"
IMG=352; BS=16; LR=3e-4; PY="${PY:-python}"
split_name="$(basename "${SPLIT}" .json)"

# job = "tag|epochs|flags"  (flags passed identically to train + eval)
JOBS=(
  "ctd_base|200|--ctdnet-loss bce --disable-ctdnet-semantic --disable-ctdnet-boundary"
  "ctd_sem|200|--ctdnet-loss bce --disable-ctdnet-boundary"
  "ctd_full|200|--ctdnet-loss bce"
  "ctd_nocam|200|--ctdnet-loss bce --disable-ctdnet-cam"
  "ctd_full_struct|200|--ctdnet-loss structure"
  "ctd_full_hybrid|200|--ctdnet-loss hybrid"
  "ctd_full_e60|60|--ctdnet-loss bce"
  "ctd_base_e60|60|--ctdnet-loss bce --disable-ctdnet-semantic --disable-ctdnet-boundary"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r tag epochs flags <<< "${job}"
  out="${ROOT}/${split_name}/${tag}"
  echo "[gpu ${GPU_ID}] === ${tag} (e${epochs}) ==="
  if [ -f "${out}/best.pt" ] && [ -f "${out}/test_metrics.json" ]; then echo "[gpu ${GPU_ID}] skip: ${tag}"; continue; fi
  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --model ctdnet_r18 --pretrained --split-file "${SPLIT}" \
      --image-size ${IMG} --batch-size ${BS} --epochs "${epochs}" --lr ${LR} \
      --device cuda --gpu-ids 0 --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" ${flags} || { echo "[gpu ${GPU_ID}] TRAIN FAIL: ${tag}"; continue; }
  fi
  PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
    --model ctdnet_r18 --pretrained --split-file "${SPLIT}" --split test \
    --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
    --checkpoint "${out}/best.pt" --output-dir "${out}" ${flags} \
    || echo "[gpu ${GPU_ID}] EVAL FAIL: ${tag}"
done
echo "[gpu ${GPU_ID}] ctdnet worker ${WORKER_INDEX} done."
