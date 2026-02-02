
FROM python:3.10-slim
WORKDIR /asr
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi==0.115.6 uvicorn[standard]==0.30.6 python-multipart==0.0.9 faster-whisper==1.0.3 requests==2.32.3

COPY server.py .
ENV WHISPER_MODEL=base
ENV WHISPER_MODEL_PATH=
CMD ["uvicorn","server:app","--host","0.0.0.0","--port","9000"]
