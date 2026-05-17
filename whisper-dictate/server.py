from fastapi import FastAPI, UploadFile, File
from faster_whisper import WhisperModel
import io
import time

MODEL_ID = "deepdml/faster-whisper-large-v3-turbo"

app = FastAPI()

print(f"Loading {MODEL_ID} onto CUDA (FP16)...")
model = WhisperModel(MODEL_ID, device="cuda", compute_type="float16")
print("Model ready.")


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL_ID}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    t0 = time.perf_counter()
    audio_bytes = await file.read()
    segments, info = model.transcribe(
        io.BytesIO(audio_bytes),
        beam_size=1,
        vad_filter=True,
        language="en",
    )
    text = " ".join(s.text for s in segments).strip()
    return {
        "text": text,
        "duration_s": info.duration,
        "elapsed_s": round(time.perf_counter() - t0, 3),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
