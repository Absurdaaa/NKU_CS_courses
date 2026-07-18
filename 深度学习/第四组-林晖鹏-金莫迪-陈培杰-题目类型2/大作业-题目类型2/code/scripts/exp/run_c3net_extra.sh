#!/usr/bin/env bash
# Extra C3Net experiments to keep idle GPUs busy:
#   - e60 BCE ablation chain (less overfitting -> hopefully monotone "each module helps")
#   - regularization / strength variants on the best model (b4_full)
#
#   ./run_c3net_extra.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"

DATA_ROOT="data/ECSSD"; ROOT="runs/c3net_ablation"; SPLIT="splits/trainval_seed_42.json"
IMG=352; BS=16; LR=3e-4; PY="${PY:-python}"
split_name="$(basename "${SPLIT}" .json)"

# job = "tag|epochs|augmode|flags"
JOBS=(
  "e60_a0_base|60|basic|--c3net-loss bce --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "e60_b2_context|60|basic|--c3net-loss bce --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "e60_b3_cue|60|basic|--c3net-loss bce --disable-c3net-cscm"
  "e60_b4_full|60|basic|--c3net-loss bce"
  "b4_full_wd1e4|200|basic|--c3net-loss bce --weight-decay 1e-4"
  "b4_full_wd5e4|200|basic|--c3net-loss bce --weight-decay 5e-4"
  "b4_full_gamma2|200|basic|--c3net-loss bce --c3net-cscm-gamma 2.0"
  "b4_full_augwd|200|full|--c3net-loss bce --weight-decay 1e-4"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r tag epochs augmode flags <<< "${job}"
  out="${ROOT}/${split_name}/${tag}"
  echo "[gpu ${GPU_ID}] === ${tag} (e${epochs}, aug=${augmode}) ==="
  if [ -f "${out}/best.pt" ] && [ -f "${out}/test_metrics.json" ]; then
    echo "[gpu ${GPU_ID}] skip (complete): ${tag}"; continue
  fi
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
echo "[gpu ${GPU_ID}] extra worker ${WORKER_INDEX} done."
