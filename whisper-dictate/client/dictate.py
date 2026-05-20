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

# Optional LLM correction step (Ollama). If CORRECTION_URL is unset, this step is skipped.
CORRECTION_URL = os.environ.get("CORRECTION_URL")  # e.g. http://192.168.1.175:11434/api/generate
CORRECTION_MODEL = os.environ.get("CORRECTION_MODEL", "qwen2.5:0.5b")

SAMPLE_RATE = 16000

GLOSSARY_FILE = HERE / "glossary.txt"
RECENT_MAXLEN = 8
# whisper.cpp accepts ~224 tokens of prompt (roughly 900 chars). Stay under that
# but use most of the budget. Glossary is always preserved; only recent gets trimmed.
PROMPT_BUDGET_CHARS = 800


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


CORRECTION_SYSTEM = (
    "You correct speech-to-text transcription mistakes. "
    "Given a raw transcript, output ONLY the corrected text — no quotes, prefix, or commentary. "
    "Keep meaning exactly the same. Do not paraphrase. "
    "Only fix obvious mistakes using the domain context below.\n\n"
    f"Domain context: {GLOSSARY}"
)


def _correct(text: str) -> str:
    """Optional LLM post-correction. Returns text unchanged if Ollama is unreachable or disabled."""
    if not CORRECTION_URL or not text:
        return text
    try:
        r = requests.post(
            CORRECTION_URL,
            json={
                "model": CORRECTION_MODEL,
                "system": CORRECTION_SYSTEM,
                "prompt": text,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 256},
            },
            timeout=10,
        )
        r.raise_for_status()
        out = r.json().get("response", "").strip()
        # strip surrounding quotes if the model wrapped output despite instructions
        if len(out) >= 2 and out[0] in "\"'" and out[-1] == out[0]:
            out = out[1:-1].strip()
        return out or text
    except Exception as e:
        print(f"correction err: {e}")
        return text


def _build_prompt() -> str:
    """Always preserve glossary; trim recent transcripts from the front to fit budget."""
    glossary = GLOSSARY[:PROMPT_BUDGET_CHARS]
    if not recent:
        return glossary
    remaining = PROMPT_BUDGET_CHARS - len(glossary) - 1
    if remaining <= 0:
        return glossary
    recent_text = " ".join(recent)
    if len(recent_text) > remaining:
        recent_text = recent_text[-remaining:]  # keep most recent
    return f"{glossary} {recent_text}".strip() if glossary else recent_text

# Hold Option + Control (either side) to record.
MOD_ALT = {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr}
MOD_CTRL = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}

kb = Controller()
audio_buf: list[np.ndarray] = []
is_recording = False
stream: sd.InputStream | None = None
held: set = set()

# Safety net for stuck mic: if recording exceeds this many seconds without
# a release event (pynput sometimes drops modifier releases on macOS),
# force-stop and recover state.
MAX_RECORD_SECONDS = float(os.environ.get("MAX_RECORD_SECONDS", "60"))
_max_record_timer: threading.Timer | None = None


_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _on_audio(indata, frames, t, status):
    if is_recording:
        audio_buf.append(indata.copy())


def _start():
    global is_recording, audio_buf, stream, _max_record_timer
    if is_recording:
        return
    audio_buf = []
    is_recording = True
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=_on_audio)
    stream.start()
    _max_record_timer = threading.Timer(MAX_RECORD_SECONDS, _force_stop)
    _max_record_timer.daemon = True
    _max_record_timer.start()
    print("rec...", flush=True)


def _force_stop():
    """Safety net: pynput sometimes loses modifier-release events on macOS,
    which leaves the mic stuck on. After MAX_RECORD_SECONDS, force-stop and
    clear the held-modifier cache so the next combo press works."""
    if not is_recording:
        return
    print(f"max record duration ({MAX_RECORD_SECONDS}s) reached; force-stopping", flush=True)
    held.clear()
    _stop_and_send()


def _stop_and_send():
    """Run on the listener thread. Must return fast — everything heavy goes to a worker."""
    global is_recording, stream, _max_record_timer
    if not is_recording:
        return
    is_recording = False
    if _max_record_timer is not None:
        _max_record_timer.cancel()
        _max_record_timer = None
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

    dt_whisper = time.perf_counter() - t0
    text = _clean(text)

    t1 = time.perf_counter()
    corrected = _correct(text)
    dt_correct = time.perf_counter() - t1

    if corrected != text:
        print(f"{dt_whisper:.2f}s whisper, {dt_correct:.2f}s correct: {text!r} -> {corrected!r}")
    else:
        print(f"{dt_whisper:.2f}s: {corrected!r}")

    if corrected:
        recent.append(corrected)
        kb.type(corrected + " ")


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
