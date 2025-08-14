import os
import asyncio
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from openai_realtime_client import RealtimeClient, TurnDetectionMode, WsHandler
from llama_index.core.tools import FunctionTool, ToolMetadata
from tools import get_current_time, get_current_date, query_rag

# Load environment variables
load_dotenv()

# Initialize tools
class NoArgsSchema(BaseModel):
    pass

class RagArgsSchema(BaseModel):
    query: str

tools = [
    FunctionTool(
        fn=get_current_time,
        metadata=ToolMetadata(
            name="get_current_time",
            description="Devuelve la hora actual en formato HH:MM y la zona horaria configurada",
            fn_schema=NoArgsSchema
        ),
        # async_fn, callback, async_callback, partial_params quedan en None
    ),
    FunctionTool(
        fn=get_current_date,
        metadata=ToolMetadata(
            name="get_current_date",
            description="Devuelve la fecha actual en formato DD:MM y la zona horaria configurada",
            fn_schema=NoArgsSchema
        ),
    ),
    FunctionTool(
        fn=query_rag,
        metadata=ToolMetadata(
            name="query_rag",
            description="Consulta la documentación para responder preguntas relativas a la Casa de los balcones.",
            fn_schema=RagArgsSchema
        ),
    ),
]

app = FastAPI()

@app.get("/health", response_class=JSONResponse)
async def health_check():
    return {"message": "Realtime Assistant server is running!"}

@app.websocket("/ws")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    ws_handler = WsHandler(websocket)

    client = RealtimeClient(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL"),
        on_text_delta=lambda text: print(f"\nAssistant: {text}", end="", flush=True),
        on_audio_delta=lambda audio: asyncio.create_task(ws_handler.send_audio(audio)),
        on_input_transcript=lambda t: print(f"\nYou said: {t}\nAssistant: ", end="", flush=True),
        on_output_transcript=lambda t: print(f"{t}", end="", flush=True),
        on_interrupt=lambda: asyncio.create_task(ws_handler.send_clear_event()),
        turn_detection_mode=TurnDetectionMode.SEMANTIC_VAD,
        language="es",
        tools=tools,
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

# Serve static files
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    print("Starting Realtime Assistant server...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
