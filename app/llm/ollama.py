
import httpx
from ..config import OLLAMA_BASE_URL, OLLAMA_MODEL

async def ollama_generate(prompt: str) -> str:
    url=f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    async with httpx.AsyncClient(timeout=60) as client:
        r=await client.post(url, json=payload)
        r.raise_for_status()
        return r.json().get("response","").strip()
