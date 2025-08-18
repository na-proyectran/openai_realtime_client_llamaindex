import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from openai_realtime_client import (
    RealtimeClient,
    TurnDetectionMode,
    RtcHandler,
    ConnectionMode,
)

load_dotenv()

app = FastAPI()


class Offer(BaseModel):
    sdp: str


@app.get("/health", response_class=JSONResponse)
async def health_check():
    """Simple health check endpoint."""
    return {"message": "Unity Realtime WebRTC server running"}


@app.post("/offer")
async def unity_webrtc_endpoint(offer: Offer):
    """Handle WebRTC offer from Unity and stream audio with the Realtime API."""
    rtc_handler = RtcHandler()

    transport = ConnectionMode.WEBRTC if os.getenv("OPENAI_TRANSPORT", "webrtc").lower() == "webrtc" else ConnectionMode.WEBSOCKET

    client = RealtimeClient(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL"),
        on_audio_delta=lambda audio: asyncio.create_task(rtc_handler.send_audio(audio)),
        on_text_delta=lambda text: print(f"\nAssistant: {text}", end="", flush=True),
        on_input_transcript=lambda t: print(f"\nUser: {t}\nAssistant: ", end="", flush=True),
        on_interrupt=lambda: asyncio.create_task(rtc_handler.send_clear_event()),
        language="es",
        turn_detection_mode=TurnDetectionMode.SEMANTIC_VAD,
        connection_mode=transport,
    )

    await client.connect()
    await rtc_handler.start_streaming(client)
    asyncio.create_task(client.handle_messages())
    answer_sdp = await rtc_handler.create_answer(offer.sdp)
    return {"sdp": answer_sdp}


if __name__ == "__main__":
    print("Starting Realtime WebRTC server...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
