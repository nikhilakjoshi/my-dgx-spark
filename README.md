# my-dgx-spark

Personal tooling that runs on my NVIDIA DGX Spark. Tracks every service I deploy on the box and any companion clients (Macs, etc.) that use them.

## What's here

### `whisper-dictate/` — low-latency push-to-talk dictation

`whisper.cpp` (large-v3-turbo, CUDA 13, Blackwell GB10) runs as a `systemd --user` service on the Spark. A Python client on macOS captures mic audio on a global hotkey and POSTs it to the Spark; the transcript types at the cursor.

Architecture:

```
Mac (hold Option+Ctrl, speak)
  |  audio -> POST /transcribe
  v
DGX Spark :8000  (whisper-server, whisper.cpp + CUDA 13)
  |  text
  v
Mac  (kb.type at cursor)
```

Components:

- `whisper-dictate/run-server.sh` — launches whisper-server with the right flags
- `whisper-dictate/systemd/whisper-server.service` — systemd `--user` unit for the Spark
- `whisper-dictate/client/dictate.py` — Mac push-to-talk client
- `whisper-dictate/client/dictate.sh` — background runner (`start | stop | status | logs | restart`)
- `whisper-dictate/client/.env.example` — `SPARK_URL` template

## Setup

- **DGX Spark (server):** [`docs/spark-ops.md`](docs/spark-ops.md) — install, monitor, edit, troubleshoot the systemd service
- **Mac (client), corporate / Zscaler:** [`docs/corporate-mac-setup.md`](docs/corporate-mac-setup.md) — clone, perms, Zscaler diagnostic, SSH tunnel fallback
- **Mac (client), personal:** same as corporate doc minus the Zscaler section

## Future work (parked)

- [`docs/future-prompt-biasing.md`](docs/future-prompt-biasing.md) — fix domain-term misspellings (Whisper, DGX Spark, etc.) via whisper.cpp's per-request `prompt` field. No second model. Cheapest win.
- [`docs/future-llm-postprocess.md`](docs/future-llm-postprocess.md) — LLM-formatted dictation (markdown mode, cleanup, polish) with a second hotkey. Heavier.
