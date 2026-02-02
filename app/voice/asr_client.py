
import httpx
from ..config import ASR_BASE_URL

async def transcribe_audio(file_bytes: bytes, filename: str):
    url=f"{ASR_BASE_URL.rstrip('/')}/asr/transcribe"
    files={"file": (filename, file_bytes, "application/octet-stream")}
    async with httpx.AsyncClient(timeout=120) as client:
        r=await client.post(url, files=files)
        r.raise_for_status()
        return r.json()
