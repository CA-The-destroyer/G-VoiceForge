FROM node:22-bookworm-slim AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
FROM python:3.11-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 ffmpeg libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128 && pip install --no-cache-dir -r requirements.txt
COPY voiceforge/ voiceforge/
COPY scripts/ scripts/
COPY unreal/ unreal/
COPY --from=frontend /ui/dist frontend/dist/
ENV VOICEFORGE_DATA=/data VOICEFORGE_MODELS=/models VOICEFORGE_OFFLINE=1
EXPOSE 8765
CMD ["python","-m","uvicorn","voiceforge.backend.api.app:app","--host","0.0.0.0","--port","8765","--workers","1"]
