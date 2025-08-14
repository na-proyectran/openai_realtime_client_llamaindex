import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
        # Opcional: limpiar output si hay interrupciones/cortes
        on_interrupt=lambda: asyncio.create_task(ws_handler.send_clear_event()),
        language="es",
        turn_detection_mode=TurnDetectionMode.SEMANTIC_VAD,
    )

    tasks = []
    try:
        await client.connect()
        print("Connected to OpenAI Realtime API!\n")

        # Lanza tareas concurrentes
        tasks.append(asyncio.create_task(client.handle_messages()))
        tasks.append(asyncio.create_task(ws_handler.start_streaming(client)))

        # Mantiene vivo el endpoint hasta que alguna falle o el cliente cierre
        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_EXCEPTION
        )

        # Propaga la primera excepción (si la hubo)
        for d in done:
            exc = d.exception()
            if exc:
                raise exc

    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        for t in tasks:
            t.cancel()
        await ws_handler.stop_streaming()
        await client.close()


if __name__ == "__main__":
    print("Starting Realtime Assistant server...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)