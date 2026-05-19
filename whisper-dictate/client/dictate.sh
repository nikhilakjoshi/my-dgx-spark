#!/usr/bin/env bash
# Background runner for dictate.py.
# Launch from a terminal that already has Accessibility + Input Monitoring + Microphone
# granted (e.g. Terminal.app, iTerm, or VS Code). The Python child inherits the terminal's
# TCC responsibility, so permissions keep working even after you close the terminal.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$HERE/.venv"
LOG_DIR="$HOME/Library/Logs"
LOG="$LOG_DIR/whisper-dictate.log"
PIDFILE="$HERE/.dictate.pid"
HEARTBEAT="$HERE/.dictate.heartbeat"
HEARTBEAT_STALE_SECONDS=45  # 3x interval in dictate.py

cmd="${1:-status}"

_running() {
  [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

case "$cmd" in
  start)
    if _running; then
      echo "already running, pid $(cat "$PIDFILE")"
      exit 0
    fi
    mkdir -p "$LOG_DIR"
    cd "$HERE"
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    PYTHONUNBUFFERED=1 nohup python dictate.py >> "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    disown || true
    echo "started, pid $(cat "$PIDFILE")"
    echo "log:    $LOG"
    ;;
  stop)
    if _running; then
      pid="$(cat "$PIDFILE")"
      kill "$pid"
      rm -f "$PIDFILE" "$HEARTBEAT"
      echo "stopped pid $pid"
    else
      echo "not running"
      rm -f "$PIDFILE" "$HEARTBEAT"
    fi
    ;;
  restart)
    "$0" stop || true
    sleep 0.5
    "$0" start
    ;;
  status)
    if ! _running; then
      echo "stopped"
      exit 0
    fi
    pid="$(cat "$PIDFILE")"
    if [[ ! -f "$HEARTBEAT" ]]; then
      echo "running pid $pid, no heartbeat yet (just started — wait a few seconds)"
      exit 0
    fi
    now=$(date +%s)
    beat=$(stat -f %m "$HEARTBEAT")
    age=$((now - beat))
    if (( age > HEARTBEAT_STALE_SECONDS )); then
      echo "running pid $pid, BUT heartbeat is ${age}s old (likely stalled after sleep/wake)."
      echo "suggest: $(basename "$0") restart"
      exit 1
    fi
    echo "running pid $pid, healthy (heartbeat ${age}s ago)"
    ;;
  logs)
    tail -f "$LOG"
    ;;
  clear-log)
    was_running=0
    if _running; then
      was_running=1
      "$0" stop
    fi
    if [[ -f "$LOG" ]]; then
      bak="$LOG.bak.$(date +%Y%m%d-%H%M%S)"
      mv "$LOG" "$bak"
      echo "archived: $bak"
    else
      echo "no log to clear"
    fi
    if (( was_running )); then
      "$0" start
    fi
    ;;
  *)
    echo "usage: $(basename "$0") {start|stop|restart|status|logs|clear-log}" >&2
    exit 2
    ;;
esac
