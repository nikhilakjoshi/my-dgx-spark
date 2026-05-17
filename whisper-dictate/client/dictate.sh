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
    nohup python dictate.py >> "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    disown || true
    echo "started, pid $(cat "$PIDFILE")"
    echo "log:    $LOG"
    ;;
  stop)
    if _running; then
      pid="$(cat "$PIDFILE")"
      kill "$pid"
      rm -f "$PIDFILE"
      echo "stopped pid $pid"
    else
      echo "not running"
      rm -f "$PIDFILE"
    fi
    ;;
  restart)
    "$0" stop || true
    sleep 0.5
    "$0" start
    ;;
  status)
    if _running; then
      echo "running, pid $(cat "$PIDFILE")"
    else
      echo "stopped"
    fi
    ;;
  logs)
    tail -f "$LOG"
    ;;
  *)
    echo "usage: $(basename "$0") {start|stop|restart|status|logs}" >&2
    exit 2
    ;;
esac
