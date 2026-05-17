# Spark ops — whisper-server systemd service

Operational notes for the `whisper-server.service` running on the DGX Spark under systemd `--user`.

Unit file: `whisper-dictate/systemd/whisper-server.service` (in this repo) → installed to `~/.config/systemd/user/whisper-server.service` on the Spark.

## Install from scratch (Spark)

Run on the Spark via `ssh spark`.

```bash
# 1. Repo cloned to ~/Projects/whisper-dictate (whisper.cpp built, model downloaded)
# 2. Install unit
mkdir -p ~/.config/systemd/user
cp ~/Projects/whisper-dictate/systemd/whisper-server.service ~/.config/systemd/user/

# 3. One-time: keep user services running without active login (needs sudo password)
sudo loginctl enable-linger nikhilakjoshi

# 4. Load + enable + start
systemctl --user daemon-reload
systemctl --user enable --now whisper-server

# 5. Verify
systemctl --user status whisper-server
ss -ltn | grep :8000
```

## Monitor

```bash
# tail logs live
journalctl --user -u whisper-server -f

# recent history
journalctl --user -u whisper-server --since "1 hour ago"
journalctl --user -u whisper-server -n 200

# status + last lines + restart count
systemctl --user status whisper-server
```

## Edit and apply

**Change whisper-server flags** (edit `run-server.sh`):

```bash
# on dev mac
$EDITOR whisper-dictate/run-server.sh
scp whisper-dictate/run-server.sh spark:~/Projects/whisper-dictate/
ssh spark 'systemctl --user restart whisper-server'
```

**Change service config** (edit `.service` unit):

```bash
# on dev mac
$EDITOR whisper-dictate/systemd/whisper-server.service
scp whisper-dictate/systemd/whisper-server.service spark:~/.config/systemd/user/
ssh spark 'systemctl --user daemon-reload && systemctl --user restart whisper-server'
```

## Start / stop / disable

```bash
systemctl --user restart whisper-server
systemctl --user stop whisper-server
systemctl --user start whisper-server
systemctl --user disable whisper-server     # remove from autostart, leave installed
systemctl --user disable --now whisper-server  # stop AND remove from autostart
```

## Uninstall

```bash
ssh spark '
systemctl --user disable --now whisper-server
rm ~/.config/systemd/user/whisper-server.service
systemctl --user daemon-reload
'
# optional: drop linger
ssh spark 'sudo loginctl disable-linger nikhilakjoshi'
```

## Troubleshooting

- **Port 8000 already in use** → a manual `whisper-server` is still running. `pkill whisper-server` then retry.
- **Service activates but no listener on :8000** → check logs, usually a CUDA load or model-path failure. `journalctl --user -u whisper-server -n 100`.
- **`nvcc`/CUDA not found** at startup → the unit hardcodes `PATH=/usr/local/cuda-13.0/bin:...`; verify that path still exists after a CUDA upgrade.
- **Linger lost after reboot** → re-run `sudo loginctl enable-linger nikhilakjoshi`. Confirm with `loginctl show-user nikhilakjoshi | grep Linger`.
- **Model not loaded** → confirm `~/Projects/whisper-dictate/whisper.cpp/models/ggml-large-v3-turbo.bin` exists and is ~1.6 GB.
- **Need to force a fresh CUDA init** → `systemctl --user restart whisper-server` (5-10 s while model reloads).

## Quick reachability test from a client mac

```bash
curl -sv -m 5 http://192.168.1.175:8000/transcribe -X POST -F file=@/dev/null 2>&1 | head -10
# any HTTP response = server reachable
```
