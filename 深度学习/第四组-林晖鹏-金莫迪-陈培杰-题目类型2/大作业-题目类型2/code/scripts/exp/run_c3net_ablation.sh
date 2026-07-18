#!/usr/bin/env bash
# C3Net-R18 ablation sweep.
#
# Each job trains a single-GPU C3Net config (so the custom compute_loss is not
# bypassed by DataParallel) and evaluates it on the ECSSD test split. Jobs are
# sharded across workers by index so several can run in parallel, one per GPU:
#
#   ./run_c3net_ablation.sh <gpu_id> <worker_index> <num_workers>
#
# Launch one process per GPU, e.g. for 4 GPUs:
#   for w in 0 1 2 3; do ./run_c3net_ablation.sh $w $w 4 & done; wait
#
# Idempotent: a job whose best.pt + test_metrics.json already exist is skipped;
# a job with best.pt but no metrics is only re-evaluated.
set -uo pipefail

GPU_ID="${1:-0}"
WORKER_INDEX="${2:-0}"
NUM_WORKERS="${3:-1}"

DATA_ROOT="data/ECSSD"
ROOT_OUTPUT="runs/c3net_ablation"
IMG=352
BS=16
EPOCHS=200
LR=3e-4
PY="${PY:-python}"

SEED42="splits/trainval_seed_42.json"
SEED3407="splits/trainval_seed_3407.json"
SEED2026="splits/trainval_seed_2026.json"

# Architecture-affecting flags are passed identically to train.py and eval.py.
# job = "split_file|tag|flags"
#
# Order matters: with NUM_WORKERS=4 the first 4 jobs (one per worker/GPU) form
# wave 1 -- the hypothesis-validation set (base, full, +structure, +CSCM-only).
# We check full >= base after wave 1 before trusting the rest of the sweep.
JOBS=(
  # ---- WAVE 1: validate the core hypothesis (one per GPU) ----
  "${SEED42}|a0_base|--c3net-loss bce --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "${SEED42}|a4_full|--c3net-loss structure"
  "${SEED42}|a1_struct|--c3net-loss structure --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "${SEED42}|s_cscm_only|--c3net-loss structure --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup"
  # ---- WAVE 2: rest of the cumulative ablation (seed 42) ----
  "${SEED42}|a2_context|--c3net-loss structure --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "${SEED42}|a3_cue|--c3net-loss structure --disable-c3net-cscm"
  "${SEED42}|c_single7|--c3net-loss structure --c3net-cscm-scales 7"
  "${SEED42}|c_pure|--c3net-loss structure --c3net-cscm-gating pure"
  # ---- WAVE 3: multi-seed robustness for the two ENDPOINTS only ----
  # 300-image test is noisy, but repeating every row over 3 seeds is too slow.
  # Compromise: only the endpoints (base, full) -- the load-bearing "full >= base"
  # claim -- get 3 seeds (42/3407/2026, fixed test) for mean+/-std. The
  # intermediate rows stay single-seed (seed 42) to show the cumulative trend.
  "${SEED3407}|a0_base|--c3net-loss bce --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "${SEED3407}|a4_full|--c3net-loss structure"
  "${SEED2026}|a0_base|--c3net-loss bce --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "${SEED2026}|a4_full|--c3net-loss structure"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then
    idx=$(( idx + 1 )); continue
  fi
  idx=$(( idx + 1 ))

  IFS='|' read -r split_file tag flags <<< "${job}"
  split_name="$(basename "${split_file}" .json)"
  out="${ROOT_OUTPUT}/${split_name}/${tag}"

  echo "[gpu ${GPU_ID}] === ${split_name}/${tag} ==="

  if [ -f "${out}/best.pt" ] && [ -f "${out}/test_metrics.json" ]; then
    echo "[gpu ${GPU_ID}] skip (already complete): ${out}"
    continue
  fi

  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --model c3net_r18 --pretrained \
      --split-file "${split_file}" \
      --image-size ${IMG} --batch-size ${BS} --epochs ${EPOCHS} --lr ${LR} \
      --device cuda --gpu-ids 0 \
      --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" \
      ${flags} || { echo "[gpu ${GPU_ID}] TRAIN FAILED: ${tag}"; continue; }
  fi

  PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
    --model c3net_r18 --pretrained \
    --split-file "${split_file}" --split test \
    --image-size ${IMG} --batch-size ${BS} \
    --device cuda --gpu-ids 0 \
    --checkpoint "${out}/best.pt" \
    --output-dir "${out}" \
    ${flags} || echo "[gpu ${GPU_ID}] EVAL FAILED: ${tag}"
done

echo "[gpu ${GPU_ID}] worker ${WORKER_INDEX} done."
