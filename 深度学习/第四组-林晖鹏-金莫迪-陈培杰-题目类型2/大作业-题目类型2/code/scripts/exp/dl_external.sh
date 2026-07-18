#!/usr/bin/env bash
# Download external SOD test datasets (DUTS-TE, DUT-OMRON) into basic/data/_ext.
set -uo pipefail
cd /home/ubuntu/lhp/deep-learning/basic/data
mkdir -p _ext && cd _ext
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY

echo "[1/3] DUTS-TE.zip (~140MB)"
curl -L --retry 5 -C - -sS -o DUTS-TE.zip \
  http://saliencydetection.net/duts/download/DUTS-TE.zip
echo "[2/3] DUT-OMRON-image.zip"
curl -L --retry 5 -C - -sS -o DUT-OMRON-image.zip \
  http://saliencydetection.net/dut-omron/download/DUT-OMRON-image.zip
echo "[3/3] DUT-OMRON-gt.zip"
curl -L --retry 5 -C - -sS -o DUT-OMRON-gt.zip \
  http://saliencydetection.net/dut-omron/download/DUT-OMRON-gt-pixelwise.zip.zip

echo "ALL_DOWNLOADED"
ls -la *.zip
