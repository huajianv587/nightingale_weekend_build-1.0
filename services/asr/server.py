
from fastapi import FastAPI, UploadFile, File, HTTPException
from faster_whisper import WhisperModel
import os, tempfile

app = FastAPI(title="ASR (faster-whisper)")
_model = None

def get_model():
    global _model
    if _model is not None:
        return _model
    model_path = os.getenv("WHISPER_MODEL_PATH") or ""
    model_name = os.getenv("WHISPER_MODEL") or "base"
    if model_path and os.path.exists(model_path) and os.listdir(model_path):
        _model = WhisperModel(model_path, device="cpu", compute_type="int8")
    else:
        _model = WhisperModel(model_name, device="cpu", compute_type="int8")
    return _model

@app.post("/asr/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="missing file")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    model = get_model()
    segments, info = model.transcribe(tmp_path)
    text = " ".join([seg.text.strip() for seg in segments]).strip()
    try:
        os.remove(tmp_path)
    except Exception:
        pass
    return {"transcript": text, "confidence": 0.9, "language": getattr(info, "language", None)}
