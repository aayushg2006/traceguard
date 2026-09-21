FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRACEGUARD_APP_HOST=0.0.0.0 \
    TRACEGUARD_APP_PORT=8000 \
    TRACEGUARD_OLLAMA_URL=http://127.0.0.1:11434 \
    TRACEGUARD_CHROMA_DIR=/app/data/chroma

WORKDIR /app
RUN groupadd --system traceguard \
    && useradd --system --gid traceguard --create-home traceguard

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY config ./config
RUN mkdir -p /app/data/chroma \
    && chown -R traceguard:traceguard /app

USER traceguard
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('TRACEGUARD_APP_PORT', '8000') + '/health', timeout=3)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"$TRACEGUARD_APP_HOST\" --port \"$TRACEGUARD_APP_PORT\""]
