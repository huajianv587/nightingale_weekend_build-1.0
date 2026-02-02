
# Nightingale Closed Loop — Full End-to-End (MySQL + Whisper ASR + Ollama Qwen2 + Realtime)

## One-command run (Docker)
```bash
docker compose up --build
```

Open:
- Patient UI: http://localhost:8000/patient
- Clinician UI: http://localhost:8000/clinician

Seed logins:
- patient@demo.example.com / password
- clinician@demo.example.com / password

## Voice flow (closed loop)
Patient UI supports audio upload -> ASR -> transcript -> redaction -> risk -> memory -> escalation -> clinician reply -> patient chat (realtime WebSocket).

## GRIP DB schema
`db/init.sql` contains CREATE DATABASE + CREATE TABLE + columns.

## Run unit tests (SQLite in-memory)
```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
