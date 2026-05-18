"""Push-to-talk dictation client. Hold Option + Ctrl, speak, release to insert."""
import collections
import io
import os
import re
import sys
import threading
import time
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf
from dotenv import load_dotenv
from pynput import keyboard
from pynput.keyboard import Controller

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

HEARTBEAT_FILE = HERE / ".dictate.heartbeat"
HEARTBEAT_INTERVAL = 15  # seconds


def _heartbeat_loop():
    while True:
        try:
            HEARTBEAT_FILE.touch()
        except Exception:
            pass
        time.sleep(HEARTBEAT_INTERVAL)

SPARK_URL = os.environ.get("SPARK_URL")
if not SPARK_URL:
    sys.exit(
        "SPARK_URL not set. Copy client/.env.example to client/.env and set SPARK_URL "
        "to your DGX Spark address (e.g. http://192.168.x.x:8000/transcribe)."
    )

SAMPLE_RATE = 16000

GLOSSARY_FILE = HERE / "glossary.txt"
RECENT_MAXLEN = 8
PROMPT_BUDGET_CHARS = 500  # whisper's prompt window is small; stay well under


def _load_glossary() -> str:
    if not GLOSSARY_FILE.exists():
        return ""
    lines = []
    for line in GLOSSARY_FILE.read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            lines.append(s)
    return " ".join(lines)


GLOSSARY = _load_glossary()
recent: collections.deque[str] = collections.deque(maxlen=RECENT_MAXLEN)


def _build_prompt() -> str:
    parts = [GLOSSARY] if GLOSSARY else []
    if recent:
        parts.append(" ".join(recent))
    prompt = " ".join(parts).strip()
    if len(prompt) > PROMPT_BUDGET_CHARS:
        prompt = prompt[-PROMPT_BUDGET_CHARS:]  # keep most-recent context, drop old
    return prompt

# Hold Option + Control (either side) to record.
MOD_ALT = {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr}
MOD_CTRL = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}

kb = Controller()
audio_buf: list[np.ndarray] = []
is_recording = False
stream: sd.InputStream | None = None
held: set = set()


_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _on_audio(indata, frames, t, status):
    if is_recording:
        audio_buf.append(indata.copy())


def _start():
    global is_recording, audio_buf, stream
    if is_recording:
        return
    audio_buf = []
    is_recording = True
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=_on_audio)
    stream.start()
    print("rec...", flush=True)


def _stop_and_send():
    """Run on the listener thread. Must return fast — everything heavy goes to a worker."""
    global is_recording, stream
    if not is_recording:
        return
    is_recording = False
    s = stream
    stream = None
    chunks = list(audio_buf)
    threading.Thread(target=_finalize_and_send, args=(s, chunks), daemon=True).start()


def _finalize_and_send(s, chunks: list[np.ndarray]):
    if s is not None:
        try:
            s.stop()
            s.close()
        except Exception as e:
            print(f"stream teardown err: {e}")
    if not chunks:
        return
    audio_np = np.concatenate(chunks, axis=0)
    buf = io.BytesIO()
    sf.write(buf, audio_np, SAMPLE_RATE, format="WAV")
    buf.seek(0)

    prompt = _build_prompt()
    files = {"file": ("audio.wav", buf, "audio/wav")}
    if prompt:
        files["prompt"] = (None, prompt)

    t0 = time.perf_counter()
    try:
        r = requests.post(SPARK_URL, files=files, timeout=30)
        r.raise_for_status()
        text = r.json().get("text", "")
    except Exception as e:
        print(f"err: {e}")
        return

    dt = time.perf_counter() - t0
    text = _clean(text)
    print(f"{dt:.2f}s: {text!r}")
    if text:
        recent.append(text)
        kb.type(text + " ")


def _combo_active() -> bool:
    return any(k in held for k in MOD_ALT) and any(k in held for k in MOD_CTRL)


def on_press(key):
    held.add(key)
    if _combo_active():
        _start()


def on_release(key):
    held.discard(key)
    if is_recording and not _combo_active():
        _stop_and_send()


if __name__ == "__main__":
    print(f"dictation client -> {SPARK_URL}")
    print("hold Option + Control to dictate")
    HEARTBEAT_FILE.touch()
    threading.Thread(target=_heartbeat_loop, daemon=True).start()
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
