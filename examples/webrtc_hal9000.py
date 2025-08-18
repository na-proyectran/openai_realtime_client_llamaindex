import os
import asyncio
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from openai_realtime_client import RealtimeClient, TurnDetectionMode, RtcHandler
from llama_index.core.tools import FunctionTool, ToolMetadata
from tools import get_current_time, get_current_date, query_rag

load_dotenv()

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

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

@app.get("/health", response_class=JSONResponse)
async def health_check():
    return {"message": "Realtime WebRTC Assistant server is running!"}

class Offer(BaseModel):
    sdp: str

@app.post("/rtc")
async def handle_media_stream(offer: Offer):
    rtc_handler = RtcHandler()

    client = RealtimeClient(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL"),
        on_text_delta=lambda text: print(f"\nAssistant: {text}", end="", flush=True),
        on_audio_delta=lambda audio: asyncio.create_task(rtc_handler.send_audio(audio)),
        on_input_transcript=lambda t: print(f"\nYou said: {t}\nAssistant: ", end="", flush=True),
        on_output_transcript=lambda t: print(f"{t}", end="", flush=True),
        on_interrupt=lambda: asyncio.create_task(rtc_handler.send_clear_event()),
        turn_detection_mode=TurnDetectionMode.SEMANTIC_VAD,
        language="es",
        tools=tools,
    )

    await client.connect()
    await rtc_handler.start_streaming(client)
    asyncio.create_task(client.handle_messages())
    answer_sdp = await rtc_handler.create_answer(offer.sdp)
    return {"sdp": answer_sdp}

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    print("Starting Realtime WebRTC Assistant server...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
