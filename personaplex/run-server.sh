#!/usr/bin/env bash
# Launch NVIDIA PersonaPlex (moshi.server) on the DGX Spark.
# Requires: cd ~/Projects/personaplex/venv active. SSL cert in ./ssl/.
set -euo pipefail
ROOT="$HOME/Projects/personaplex"
SSL_DIR="$ROOT/ssl"
export HF_TOKEN="$(cat "$HOME/.cache/huggingface/token")"
source "$ROOT/venv/bin/activate"
cd "$ROOT/personaplex"
exec python -m moshi.server \
  --host 0.0.0.0 \
  --port 8998 \
  --device cuda \
  --ssl "$SSL_DIR"
