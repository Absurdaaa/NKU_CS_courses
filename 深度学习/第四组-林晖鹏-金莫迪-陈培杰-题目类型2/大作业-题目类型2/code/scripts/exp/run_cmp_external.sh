#!/usr/bin/env bash
# External validation of the comparison models (best-lr seed-42 checkpoints)
# on DUTS-TE and DUT-OMRON.  Single GPU per job.
#   ./run_cmp_external.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"
PY="${PY:-python}"; SW="runs/main_lr_sweep/trainval_seed_42"

# job = "model|lrtag|dataset|split"
JOBS=(
  "egnet_r18|lr_5em5|DUTS-TE|splits/duts_te.json"     "egnet_r18|lr_5em5|DUT-OMRON|splits/dutomron.json"
  "pfa_r18|lr_5em2|DUTS-TE|splits/duts_te.json"       "pfa_r18|lr_5em2|DUT-OMRON|splits/dutomron.json"
  "sinet_r18|lr_1em4|DUTS-TE|splits/duts_te.json"     "sinet_r18|lr_1em4|DUT-OMRON|splits/dutomron.json"
  "poolnet_r18|lr_1em4|DUTS-TE|splits/duts_te.json"   "poolnet_r18|lr_1em4|DUT-OMRON|splits/dutomron.json"
  "dss_r18|lr_5em2|DUTS-TE|splits/duts_te.json"       "dss_r18|lr_5em2|DUT-OMRON|splits/dutomron.json"
  "f3net_r18|lr_5em2|DUTS-TE|splits/duts_te.json"     "f3net_r18|lr_5em2|DUT-OMRON|splits/dutomron.json"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r model lrtag ds split <<< "${job}"
  ckpt="${SW}/${model}/${lrtag}/best.pt"
  out="runs/external_cmp/${model}_${ds}"
  [ -f "${ckpt}" ] || { echo "[gpu ${GPU_ID}] no ckpt ${model}"; continue; }
  [ -f "${out}/test_metrics.json" ] && { echo "[gpu ${GPU_ID}] skip ${model} ${ds}"; continue; }
  echo "[gpu ${GPU_ID}] === ${model} on ${ds} ==="
  PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
    --model "${model}" --pretrained --data-root "data/${ds}" --split-file "${split}" --split test \
    --image-size 352 --batch-size 16 --device cuda --gpu-ids 0 \
    --checkpoint "${ckpt}" --output-dir "${out}" \
    || echo "[gpu ${GPU_ID}] EVAL FAIL ${model} ${ds}"
done
echo "[gpu ${GPU_ID}] cmp-external worker ${WORKER_INDEX} done."
