#!/usr/bin/env bash

set -euo pipefail

# cd /Users/linshangjin/Desktop/DeepLearning/lab2

# 默认用当前分类任务里最强的 LSTM 判别器做“评委”
BEST_INFO_FILE="outputs/lstm/lstm_adam_best_lr.txt"
if [[ ! -f "${BEST_INFO_FILE}" ]]; then
  echo "Missing ${BEST_INFO_FILE}. Please run classification sweep first."
  exit 1
fi

CLASSIFIER_RUN_NAME="$(grep '^run_name=' "${BEST_INFO_FILE}" | cut -d'=' -f2-)"
CLASSIFIER_RUN_DIR="outputs/lstm/${CLASSIFIER_RUN_NAME}"

# 用法：
# 1. bash run_generation_fidelity.sh
#    优先找正式 baseline；如果没有，再回退到当前已有的 batch/smoke 结果
# 2. bash run_generation_fidelity.sh <run_dir1> <run_dir2> <run_dir3>
#    直接指定要评估的生成结果目录

if [[ "$#" -gt 0 ]]; then
  GEN_RUNS=("$@")
else
  choose_best_resampled_run() {
    local model_prefix="$1"
    find outputs/generation/resampled -maxdepth 1 -mindepth 1 -type d -name "${model_prefix}_opt*_resampled" 2>/dev/null | sort | tail -n 1
  }

  choose_best_sweep_run() {
    local model_prefix="$1"
    python3 - "$model_prefix" <<'PY'
from pathlib import Path
import csv
import sys

model_prefix = sys.argv[1]
root = Path("outputs/generation")
best_path = None
best_loss = None

for run_dir in sorted(root.glob(f"{model_prefix}_opt*")):
    summary_path = run_dir / "summary_metrics.csv"
    sample_path = run_dir / "generated_samples.txt"
    if not summary_path.exists() or not sample_path.exists():
        continue
    metrics = {}
    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if len(row) >= 2:
                metrics[row[0]] = row[1]
    if "best_train_loss" not in metrics:
        continue
    loss = float(metrics["best_train_loss"])
    if best_loss is None or loss < best_loss:
        best_loss = loss
        best_path = run_dir

if best_path is not None:
    print(best_path.as_posix())
PY
  }

  RNN_RESAMPLED_RUN="$(choose_best_resampled_run rnn_gen)"
  LSTM_RESAMPLED_RUN="$(choose_best_resampled_run lstm_gen)"
  GRU_RESAMPLED_RUN="$(choose_best_resampled_run gru_gen)"
  RNN_SWEEP_RUN="$(choose_best_sweep_run rnn_gen)"
  LSTM_SWEEP_RUN="$(choose_best_sweep_run lstm_gen)"
  GRU_SWEEP_RUN="$(choose_best_sweep_run gru_gen)"

  if [[ -n "${RNN_RESAMPLED_RUN}" ]] && [[ -n "${LSTM_RESAMPLED_RUN}" ]] && [[ -n "${GRU_RESAMPLED_RUN}" ]]; then
    GEN_RUNS=(
      "${RNN_RESAMPLED_RUN}"
      "${LSTM_RESAMPLED_RUN}"
      "${GRU_RESAMPLED_RUN}"
    )
  elif [[ -n "${RNN_SWEEP_RUN}" ]] && [[ -n "${LSTM_SWEEP_RUN}" ]] && [[ -n "${GRU_SWEEP_RUN}" ]]; then
    GEN_RUNS=(
      "${RNN_SWEEP_RUN}"
      "${LSTM_SWEEP_RUN}"
      "${GRU_SWEEP_RUN}"
    )
  elif [[ -f "outputs/generation/rnn_gen_baseline/generated_samples.txt" ]] \
    && [[ -f "outputs/generation/lstm_gen_baseline/generated_samples.txt" ]] \
    && [[ -f "outputs/generation/gru_gen_baseline/generated_samples.txt" ]]; then
    GEN_RUNS=(
      "outputs/generation/rnn_gen_baseline"
      "outputs/generation/lstm_gen_baseline"
      "outputs/generation/gru_gen_baseline"
    )
  elif [[ -f "outputs/generation/batch_smoke_rnn_gen/generated_samples.txt" ]] \
    && [[ -f "outputs/generation/batch_smoke_lstm_gen/generated_samples.txt" ]] \
    && [[ -f "outputs/generation/batch_smoke_gru_gen/generated_samples.txt" ]]; then
    GEN_RUNS=(
      "outputs/generation/batch_smoke_rnn_gen"
      "outputs/generation/batch_smoke_lstm_gen"
      "outputs/generation/batch_smoke_gru_gen"
    )
  elif [[ -f "outputs/generation/smoke_rnn_gen2/generated_samples.txt" ]] \
    && [[ -f "outputs/generation/smoke_lstm_gen2/generated_samples.txt" ]] \
    && [[ -f "outputs/generation/smoke_gru_gen2/generated_samples.txt" ]]; then
    GEN_RUNS=(
      "outputs/generation/smoke_rnn_gen2"
      "outputs/generation/smoke_lstm_gen2"
      "outputs/generation/smoke_gru_gen2"
    )
  else
    echo "No suitable generation runs found."
    echo "Either:"
    echo "  1. run bash run_sample_best_generation.sh first"
    echo "  2. or run bash sweep_lr_generation.sh first"
    echo "  3. or run bash run_generation.sh first"
    echo "  4. or pass generation run directories explicitly"
    echo
    echo "Example:"
    echo "  bash run_generation_fidelity.sh outputs/generation/your_rnn_run outputs/generation/your_lstm_run outputs/generation/your_gru_run"
    exit 1
  fi
fi

for RUN_DIR in "${GEN_RUNS[@]}"; do
  if [[ ! -f "${RUN_DIR}/generated_samples.txt" ]]; then
    echo "Missing generated samples: ${RUN_DIR}/generated_samples.txt"
    echo "Please rerun generation or pass valid run directories explicitly."
    exit 1
  fi
done

python3 evaluate_generation_fidelity.py \
  --classifier-run "${CLASSIFIER_RUN_DIR}" \
  --generation-runs "${GEN_RUNS[@]}" \
  --report-name "baseline_lstm_judge"

echo
echo "Finished generation fidelity evaluation. Check:"
echo "  outputs/generation/fidelity_reports/baseline_lstm_judge"
echo "Evaluated generation runs:"
for RUN_DIR in "${GEN_RUNS[@]}"; do
  echo "  ${RUN_DIR}"
done
echo
echo "Key files:"
echo "  fidelity_summary.csv"
echo "  overall_fidelity.png"
echo "  category_fidelity.png"
echo "  *_fidelity_confusion_matrix.png"
