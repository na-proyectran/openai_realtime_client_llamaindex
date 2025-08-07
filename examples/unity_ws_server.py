import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse

from openai_realtime_client import RealtimeClient, TurnDetectionMode, WsHandler

# Load environment variables from .env if present
load_dotenv()

app = FastAPI()


@app.get("/health", response_class=JSONResponse)
async def health_check():
    """Simple health check endpoint."""
    return {"message": "Unity Realtime server running"}


@app.websocket("/ws")
async def unity_realtime_endpoint(websocket: WebSocket):
    """Handle audio streaming between Unity and the Realtime API."""
    await websocket.accept()

    ws_handler = WsHandler(websocket)
    client = RealtimeClient(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL"),
        on_audio_delta=lambda audio: asyncio.create_task(ws_handler.send_audio(audio)),
        on_text_delta=lambda text: print(f"\nAssistant: {text}", end="", flush=True),
        on_input_transcript=lambda t: print(f"\nUser: {t}\nAssistant: ", end="", flush=True),
        language="es",
        turn_detection_mode=TurnDetectionMode.SEMANTIC_VAD,
    )

    await client.connect()
    stream_task = asyncio.create_task(ws_handler.start_streaming(client))
    handle_task = asyncio.create_task(client.handle_messages())

    try:
        await asyncio.gather(stream_task, handle_task)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await ws_handler.stop_streaming()
        await client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
