import os
import httpx

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1")

SYSTEM_PROMPT = """You are a helpful clinical assistant.
You must be safe: no diagnosis, provide general guidance, ask clarifying questions.
You should respond differently depending on user input.
If input is vague, ask 1-3 follow-up questions.
Output plain text only.
"""

async def generate_reply(history_messages, patient_text: str) -> str:
    """
    history_messages: list of dicts like [{"role":"user"/"assistant","content":"..."}]
    patient_text: latest patient utterance
    """
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs.extend(history_messages[-10:])  # 取最近10条上下文
    msgs.append({"role": "user", "content": patient_text})

    payload = {
        "model": LLM_MODEL,
        "messages": msgs,
        "stream": False
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{LLM_BASE_URL}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()

    # ollama格式：{"message":{"role":"assistant","content":"..."}}
    return (data.get("message") or {}).get("content") or "I couldn’t generate a response right now."
