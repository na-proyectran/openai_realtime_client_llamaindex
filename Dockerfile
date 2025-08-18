FROM python:3.13.5-slim

# ───────────── DEPENDENCIAS DEL SISTEMA ─────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    portaudio19-dev \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# ───────────── INSTALAR POETRY 2.1.3 ─────────────
ARG POETRY_VERSION=2.1.3
ENV POETRY_HOME=/opt/poetry
ENV PATH="${POETRY_HOME}/bin:/root/.local/bin:${PATH}"

# usa el instalador oficial, fijando versión
RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION} \
 && poetry --version | grep -F "Poetry (version ${POETRY_VERSION})"

# ───────────── COPIAR TODO EL PROYECTO ─────────────
WORKDIR /app
COPY . .

# ───────────── INSTALAR DEPENDENCIAS ─────────────
# Desactiva venvs dentro del contenedor para instalar en el sistema
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --only main

# ───────────── EXPONER PUERTO ─────────────
EXPOSE 8000

# ───────────── COMANDO POR DEFECTO ─────────────
CMD ["python", "examples/hal9000_webrtc.py"]
