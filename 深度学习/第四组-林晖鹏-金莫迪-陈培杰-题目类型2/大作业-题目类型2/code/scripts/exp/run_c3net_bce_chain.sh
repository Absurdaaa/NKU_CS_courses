#!/usr/bin/env bash
# C3Net-R18 BCE ablation chain (seed 42).
#
# The structure-loss chain showed a val/test calibration gap that masked the
# architectural modules, so this chain keeps the loss as plain BCE throughout
# and stacks the three modules on top of the BCE base (a0_base, already trained):
#   base(BCE) -> +PPM -> +Edge/deep-sup -> +CSCM
# plus a BCE+CSCM-only row to isolate CSCM cleanly.
#
#   ./run_c3net_bce_chain.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail

GPU_ID="${1:-0}"
WORKER_INDEX="${2:-0}"
NUM_WORKERS="${3:-1}"

DATA_ROOT="data/ECSSD"
ROOT_OUTPUT="runs/c3net_ablation"
SPLIT="splits/trainval_seed_42.json"
IMG=352; BS=16; EPOCHS=200; LR=3e-4
PY="${PY:-python}"

# job = "tag|flags"
JOBS=(
  "b2_context|--c3net-loss bce --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "b3_cue|--c3net-loss bce --disable-c3net-cscm"
  "b4_full|--c3net-loss bce"
  "b_cscm_only|--c3net-loss bce --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup"
)

split_name="$(basename "${SPLIT}" .json)"
idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))

  IFS='|' read -r tag flags <<< "${job}"
  out="${ROOT_OUTPUT}/${split_name}/${tag}"
  echo "[gpu ${GPU_ID}] === ${tag} ==="

  if [ -f "${out}/best.pt" ] && [ -f "${out}/test_metrics.json" ]; then
    echo "[gpu ${GPU_ID}] skip (complete): ${out}"; continue
  fi
  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --model c3net_r18 --pretrained --split-file "${SPLIT}" \
      --image-size ${IMG} --batch-size ${BS} --epochs ${EPOCHS} --lr ${LR} \
      --device cuda --gpu-ids 0 --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" ${flags} || { echo "[gpu ${GPU_ID}] TRAIN FAILED: ${tag}"; continue; }
  fi
  PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
    --model c3net_r18 --pretrained --split-file "${SPLIT}" --split test \
    --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
    --checkpoint "${out}/best.pt" --output-dir "${out}" ${flags} \
    || echo "[gpu ${GPU_ID}] EVAL FAILED: ${tag}"
done
echo "[gpu ${GPU_ID}] bce-chain worker ${WORKER_INDEX} done."
