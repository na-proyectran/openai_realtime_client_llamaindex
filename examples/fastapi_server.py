import os
import asyncio
import base64
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from openai_realtime_client import RealtimeClient

app = FastAPI()

@app.get("/health", response_class=JSONResponse)
async def health() -> JSONResponse:
    return {"message": "Realtime Assistant server is running!"}

@app.websocket("/ws")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between a browser client and OpenAI."""
    print("Client connected")
    await websocket.accept()

    load_dotenv()

    # Forward text and audio events from OpenAI back to the websocket client
    def on_text_delta(text: str) -> None:
        asyncio.create_task(websocket.send_json({"text": text}))

    def on_audio_delta(audio: bytes) -> None:
        payload = base64.b64encode(audio).decode("utf-8")
        asyncio.create_task(websocket.send_json({"audio": payload}))

    client = RealtimeClient(
        api_key=os.environ.get("OPENAI_API_KEY"),
        model=os.environ.get("OPENAI_MODEL"),
        on_text_delta=on_text_delta,
        on_audio_delta=on_audio_delta,
    )

    await client.connect()
    handle_task = asyncio.create_task(client.handle_messages())

    try:
        async for pcm in websocket.iter_bytes():
            await client.stream_audio(pcm)
    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        await client.close()
        handle_task.cancel()
        await websocket.close()

if __name__ == "__main__":
    # pip install fastapi==0.116.0 uvicorn==0.35.0 websockets==15.0.1
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
