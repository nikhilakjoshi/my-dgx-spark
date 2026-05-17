# Corporate Mac setup (Zscaler-aware)

Setup notes for running the `whisper-dictate` client on a corporate Mac (M4 Pro), where Zscaler Client Connector intercepts network traffic.

## Context

- Server runs on the personal **DGX Spark** on the home LAN at `192.168.1.175:8000` (whisper.cpp built-in HTTP server, endpoint `/transcribe`).
- Corp Mac must reach that server from the same Wi-Fi.
- Zscaler Client Connector (ZCC) is a system-level filter. Cannot be "disconnected" — it always intercepts unless policy allows bypass.

## 1. Clone and install

```bash
git clone https://github.com/nikhilakjoshi/my-dgx-spark.git
cd my-dgx-spark/whisper-dictate/client
cp .env.example .env
# edit .env, set SPARK_URL=http://192.168.1.175:8000/transcribe (or localhost path if tunneling, see below)
python3 -m venv .venv && source .venv/bin/activate

# Corporate Zscaler / proxy often blocks pypi. Use the committed offline wheel bundle:
tar xzf wheels.tar.gz
pip install --no-index --find-links=wheels -r requirements.txt
# (If pypi works on this Mac, plain `pip install -r requirements.txt` is fine too.)

chmod +x dictate.sh   # usually preserved by git, but in case
```

The wheel bundle is built for macOS arm64 / Python 3.13. If the corp Mac has a different Python or arch, see `docs/wheel-bundle.md` to rebuild.

## 2. macOS permissions (per-app, per-machine)

Permissions DO NOT transfer from the other Mac. Grant on this Mac:

1. Quit the terminal app you'll launch `dictate.py` from (Cmd-Q).
2. System Settings -> Privacy & Security:
   - **Accessibility** -> add the terminal app, toggle on
   - **Input Monitoring** -> add the terminal app, toggle on
   - **Microphone** -> ensure terminal app enabled
3. Reopen terminal. Run `python dictate.py`. Hold Option + Ctrl to dictate.

If a corporate MDM blocks adding apps to Accessibility, contact IT — no workaround.

## 3. Zscaler diagnostic

Before assuming Zscaler blocks LAN, test direct reachability:

```bash
curl -sv -m 5 http://192.168.1.175:8000/transcribe -X POST -F file=@/dev/null 2>&1 | head -20
```

Interpret:
- `Trying 192.168.1.175:8000...` + HTTP response (any code) -> direct LAN works. ZCC bypasses RFC1918. Done.
- Trace shows `165.225.x.x` / `136.226.x.x` (Zscaler ZEN IPs) -> ZCC is tunneling. Direct LAN blocked.
- Connection refused / timeout -> either ZCC drop or other network issue (verify Wi-Fi SSID, ping Spark).

## 4. SSH tunnel fallback (if Zscaler blocks direct LAN)

ZCC almost always allows outbound SSH (port 22) to private IPs.

### a. Add SSH config on corp Mac

Append to `~/.ssh/config`:

```
Host spark
    HostName 192.168.1.175
    User nikhilakjoshi
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

Then push your key (one-time, type Spark password):

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub spark
```

Skip the keygen step if `~/.ssh/id_ed25519` already exists; otherwise:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
```

### b. Open the tunnel

```bash
ssh -N -L 8000:localhost:8000 spark
# leave this terminal open while dictating; -N = no remote shell
```

### c. Point the client at localhost

Edit `whisper-dictate/client/.env`:

```
SPARK_URL=http://localhost:8000/transcribe
```

The ZCC view: only an SSH session to a private IP. Inside the tunnel: HTTP to the Spark.

## 5. Verify and run

```bash
# direct or via tunnel, either way:
curl -s http://${SPARK_HOST:-192.168.1.175}:8000/transcribe -X POST -F file=@/dev/null
# expect HTTP 4xx (no audio is invalid input) — confirms reachability
```

Start the dictation client in the background:

```bash
./dictate.sh start      # backgrounds the python process; survives terminal close
./dictate.sh status     # is it running?
./dictate.sh logs       # tail ~/Library/Logs/whisper-dictate.log
./dictate.sh stop       # kill it
./dictate.sh restart
```

Hold **Option + Ctrl**, say something, release. Text types at the cursor.

The wrapper uses `nohup ... &`. macOS keeps TCC permissions attributed to the launching terminal app even after the terminal closes, so the granted Accessibility/Input Monitoring permissions keep working — no need to grant Python directly.

## Open issues / TODO

- Spark IP (`192.168.1.175`) is a DHCP lease. Set a router reservation or use `spark-9970.mynetworksettings.com` if it resolves on the corp Mac.
- If Zscaler also blocks SSH to private IPs, fallback path needed (e.g., port-forward through a personal server in the cloud). Cross that bridge when it appears.
