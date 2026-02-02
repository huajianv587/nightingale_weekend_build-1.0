
import os
def env(name: str, default: str=""):
    v = os.getenv(name)
    return v if v is not None else default

DATABASE_URL = "mysql+pymysql://nightingale:nightingale@mysql:3306/nightingale_grip?charset=utf8mb4"
JWT_SECRET = env("JWT_SECRET", "change-me")
JWT_EXPIRE_MIN = int(env("JWT_EXPIRE_MIN", "4320"))
ASR_BASE_URL = env("ASR_BASE_URL", "http://localhost:9000")
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = env("OLLAMA_MODEL", "qwen2:4b")
USE_LLM_TRIAGE = env("USE_LLM_TRIAGE", "true").lower() in ("1","true","yes","y")
