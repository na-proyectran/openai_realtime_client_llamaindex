FROM python:3.13.5-slim

# ───────────── DEPENDENCIAS DEL SISTEMA ─────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    portaudio19-dev \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# ───────────── INSTALAR POETRY ─────────────
ENV POETRY_VERSION=1.8.2
ENV PATH="/root/.local/bin:$PATH"

RUN curl -sSL https://install.python-poetry.org | python3 -

# ───────────── COPIAR TODO EL PROYECTO ─────────────
WORKDIR /app
COPY . .

# ───────────── INSTALAR DEPENDENCIAS ─────────────
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --only main

# ───────────── EXPONER PUERTO ─────────────
EXPOSE 8000

# ───────────── COMANDO POR DEFECTO ─────────────
CMD ["python", "examples/unity_ws_server.py"]
