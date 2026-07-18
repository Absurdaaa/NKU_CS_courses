#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${1:-data/ECSSD}"
SPLIT_FILES=(
  "${2:-splits/trainval_seed_42.json}"
  "${6:-splits/trainval_seed_3407.json}"
  "${7:-splits/trainval_seed_2026.json}"
)
DEVICE="${3:-cuda}"
GPU_IDS="${4:-0,1}"
ROOT_OUTPUT="${5:-runs/main_lr_sweep}"

MODELS=(
  "sinet_r18"
  "poolnet_r18"
  "dss_r18"
  "pfa_r18"
  "egnet_r18"
  "f3net_r18"
)

format_lr_dir() {
  local lr="$1"
  echo "${lr}" | sed 's/-/m/g; s/\./p/g'
}

get_lrs_for_model() {
  local model="$1"
  case "${model}" in
    sinet_r18|poolnet_r18|egnet_r18)
      echo "1e-4 3e-4 5e-4"
      ;;
    f3net_r18|dss_r18)
      echo "1e-3 3e-3 1e-2"
      ;;
    pfa_r18)
      echo "1e-4 3e-4 1e-3"
      ;;
    *)
      echo "1e-4 3e-4 1e-3"
      ;;
  esac
}

for split_file in "${SPLIT_FILES[@]}"; do
  split_name="$(basename "${split_file}" .json)"
  for model in "${MODELS[@]}"; do
    for lr in $(get_lrs_for_model "${model}"); do
      lr_tag="$(format_lr_dir "${lr}")"
      output_dir="${ROOT_OUTPUT}/${split_name}/${model}/lr_${lr_tag}"

      action="$(python scripts/run_guard.py \
        --output-dir "${output_dir}" \
        --expect model="${model}" \
        --expect pretrained=true \
        --expect split_file="${split_file}" \
        --expect image_size=352 \
        --expect batch_size=16 \
        --expect epochs=200 \
        --expect lr="${lr}" \
        --expect selection_metric=max_f_measure \
        --expect augment_mode=basic)"

      if [ "${action}" = "skip" ]; then
        echo "Skip training: ${output_dir} already has matching config and best.pt"
      else
        python train.py \
          --data-root "${DATA_ROOT}" \
          --split-file "${split_file}" \
          --model "${model}" \
          --pretrained \
          --image-size 352 \
          --batch-size 16 \
          --epochs 200 \
          --lr "${lr}" \
          --device "${DEVICE}" \
          --gpu-ids "${GPU_IDS}" \
          --selection-metric max_f_measure \
          --augment-mode basic \
          --output-dir "${output_dir}"
      fi

      python eval.py \
        --data-root "${DATA_ROOT}" \
        --split-file "${split_file}" \
        --split test \
        --model "${model}" \
        --pretrained \
        --image-size 352 \
        --batch-size 16 \
        --device "${DEVICE}" \
        --gpu-ids "${GPU_IDS}" \
        --checkpoint "${output_dir}/best.pt" \
        --output-dir "${output_dir}"
    done
  done
done
