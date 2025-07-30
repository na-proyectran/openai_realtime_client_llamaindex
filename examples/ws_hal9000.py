import os
import asyncio
from dotenv import load_dotenv
from pynput import keyboard
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from openai_realtime_client import RealtimeClient, TurnDetectionMode, WsHandler, InputHandler
from llama_index.core.tools import FunctionTool
from tools import get_current_time

# Load environment variables
load_dotenv()

# Initialize tools
tools = [FunctionTool.from_defaults(fn=get_current_time)]

app = FastAPI()

@app.get("/health", response_class=JSONResponse)
async def health_check():
    return {"message": "Realtime Assistant server is running!"}

@app.websocket("/ws")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    ws_handler = WsHandler(websocket)
    input_handler = InputHandler()
    input_handler.loop = asyncio.get_running_loop()

    client = RealtimeClient(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL"),
        on_text_delta=lambda text: print(f"\nAssistant: {text}", end="", flush=True),
        on_audio_delta=lambda audio: asyncio.create_task(ws_handler.send_audio(audio)),
        on_input_transcript=lambda transcript: print(f"\nYou said: {transcript}\nAssistant: ", end="", flush=True),
        on_output_transcript=lambda transcript: print(f"{transcript}", end="", flush=True),
        on_interrupt=lambda: asyncio.create_task(ws_handler.send_clear_event()),
        turn_detection_mode=TurnDetectionMode.SEMANTIC_VAD,
        language="es",
        tools=tools,
    )

    # Start keyboard listener in a separate thread
    listener = keyboard.Listener(on_press=input_handler.on_press)
    listener.start()

    try:
        await client.connect()
        asyncio.create_task(client.handle_messages())

        print("Connected to OpenAI Realtime API!")
        print("Audio streaming will start automatically.")
        print("Press 'q' to quit")
        print("")

        # Start continuous audio streaming
        asyncio.create_task(ws_handler.start_streaming(client))

        # Simple input loop for quit command
        while True:
            command, _ = await input_handler.command_queue.get()

            if command == 'q':
                break

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await ws_handler.stop_streaming()
        await client.close()

# Serve static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    print("Starting Realtime Assistant server...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
