#!/usr/bin/env bash
# Launch whisper.cpp server on the DGX Spark.
set -euo pipefail
cd "$(dirname "$0")/whisper.cpp"
exec ./build/bin/whisper-server \
  -m models/ggml-large-v3-turbo.bin \
  --host 0.0.0.0 \
  --port 8000 \
  --inference-path /transcribe \
  -l en \
  -t 16 \
  -nt
