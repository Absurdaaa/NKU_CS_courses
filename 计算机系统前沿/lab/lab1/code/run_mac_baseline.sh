#!/bin/bash

set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
FIO_BIN="${FIO_BIN:-$BASE_DIR/tools/fio-3.39/fio}"
RESULT_DIR="${RESULT_DIR:-$BASE_DIR/mac_baseline_results}"
RAW_DIR="$RESULT_DIR/raw"
TMP_DIR="$RESULT_DIR/tmp"
TEST_FILE="${TEST_FILE:-$TMP_DIR/mac_fio_test_file.bin}"
TEST_SIZE="${TEST_SIZE:-5g}"
BS="${BS:-4k}"
IOENGINE="${IOENGINE:-pvsync}"
NUMJOBS="${NUMJOBS:-1}"
IODEPTH="${IODEPTH:-1}"
KEEP_TEST_FILE="${KEEP_TEST_FILE:-1}"

if [[ ! -x "$FIO_BIN" ]]; then
  echo "fio binary not found: $FIO_BIN" >&2
  echo "Build fio first or set FIO_BIN to a valid executable." >&2
  exit 1
fi

mkdir -p "$RAW_DIR" "$TMP_DIR"

echo "Saving system information..."
{
  echo "# macOS"
  sw_vers
  echo
  echo "# Hardware"
  system_profiler SPHardwareDataType | sed -n '1,40p'
  echo
  echo "# NVMe"
  system_profiler SPNVMeDataType | sed -n '1,80p'
} > "$RESULT_DIR/system_info.txt"

echo "Creating test file: $TEST_FILE ($TEST_SIZE)"
rm -f "$TEST_FILE"
mkfile "$TEST_SIZE" "$TEST_FILE"

echo "Running seq_read ..."
"$FIO_BIN" \
  --name=seq_read \
  --ioengine="$IOENGINE" \
  --rw=read \
  --bs="$BS" \
  --size="$TEST_SIZE" \
  --numjobs="$NUMJOBS" \
  --iodepth="$IODEPTH" \
  --filename="$TEST_FILE" \
  --output-format=json \
  --output="$RAW_DIR/seq_read.json"
sync

echo "Running seq_write ..."
"$FIO_BIN" \
  --name=seq_write \
  --ioengine="$IOENGINE" \
  --rw=write \
  --bs="$BS" \
  --size="$TEST_SIZE" \
  --numjobs="$NUMJOBS" \
  --iodepth="$IODEPTH" \
  --filename="$TEST_FILE" \
  --output-format=json \
  --output="$RAW_DIR/seq_write.json"
sync

echo "Running rnd_read ..."
"$FIO_BIN" \
  --name=rnd_read \
  --ioengine="$IOENGINE" \
  --rw=randread \
  --bs="$BS" \
  --size="$TEST_SIZE" \
  --numjobs="$NUMJOBS" \
  --iodepth="$IODEPTH" \
  --filename="$TEST_FILE" \
  --output-format=json \
  --output="$RAW_DIR/rnd_read.json"
sync

echo "Running rnd_write ..."
"$FIO_BIN" \
  --name=rnd_write \
  --ioengine="$IOENGINE" \
  --rw=randwrite \
  --bs="$BS" \
  --size="$TEST_SIZE" \
  --numjobs="$NUMJOBS" \
  --iodepth="$IODEPTH" \
  --filename="$TEST_FILE" \
  --output-format=json \
  --output="$RAW_DIR/rnd_write.json"
sync

if [[ "$KEEP_TEST_FILE" != "1" ]]; then
  rm -f "$TEST_FILE"
fi

echo "Done. Raw results are in $RAW_DIR"
