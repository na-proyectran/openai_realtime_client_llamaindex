# OpenAI Realtime API Client for Python

This is an experimental OpenAI Realtime API client for Python and LlamaIndex. It integrates with LlamaIndex's tools, allowing you to quickly build custom voice assistants.

Include two examples that run directly in the terminal -- using both manual and Server VAD mode (i.e. allowing you to interrupt the chatbot).

## Installation

Install system deps:

```bash
brew install ffmpeg portaudio
```

Install python deps:

```bash
pip install openai-realtime-client

# Optional: clone the repo and run the examples locally
git clone https://github.com/run-llama/openai_realtime_client.git
cd openai_realtime_client
```

Set your OpenAI key and model by copying `.env.example` to `.env`:

```bash
cp .env.example .env
echo "OPENAI_API_KEY=sk-..." >> .env
# Optional: edit OPENAI_MODEL in .env if you want a different model
```

### RAG documents

Place any text files you want indexed under `rag_docs/` in the project root.
You can also specify another directory by setting the `RAG_DOCS_DIR`
environment variable before running the examples.

## Usage

Assuming you installed and cloned the repo (or copy-pasted the examples), you can immediately run the examples.

Run the interactive CLI with manual VAD (try asking for your phone number to see function calling in action):

```bash
python ./examples/manual_cli.py
```

Or to use streaming mode (which allows you to interrupt the chatbot):

```bash
python ./examples/streaming_cli.py
```

To proxy the Realtime API behind a simple FastAPI server:

```bash
pip install fastapi==0.116.0 uvicorn==0.35.0 websockets==15.0.1
python ./examples/ws_hal9000.py
```

## Docker

You can run the demo in a container using the provided Dockerfile. It runs
`unity_ws_server.py` by default.

Build the image:

```bash
docker build -t openai-realtime-demo .
```

Run the container (ensure `.env` contains your `OPENAI_API_KEY`):

```bash
docker run --env-file .env -p 8000:8000 openai-realtime-demo
```

This starts the FastAPI demo and exposes it on port `8000`.

### Docker Compose

The repository also includes a `docker-compose.yml` that spins up the app along
with Phoenix monitoring and a Postgres database. To build the image and start
everything:

```bash
docker compose up --build
```

The app will be available at `http://localhost:8000` and Phoenix at
`http://localhost:6006`. The compose file mounts `rag_docs/` so you can edit
documents on the host.


**NOTE:** Streaming mode can be a little janky, best to use headphones in a quiet environment.

Take a look at the examples, add your own tools, and build something amazing!

### Connection errors

`RealtimeClient.connect` logs any `OSError` or `websockets.WebSocketException`
encountered when establishing the WebSocket connection and re-raises them as a
`RuntimeError`. Ensure you handle this exception when connecting.
