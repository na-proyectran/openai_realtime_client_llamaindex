import asyncio
import os
from dotenv import load_dotenv

from pynput import keyboard
from openai_realtime_client import RealtimeClient, AudioHandler, InputHandler, TurnDetectionMode
from llama_index.core.tools import FunctionTool
from tools import get_current_time

# Add your own tools here!
# NOTE: FunctionTool parses the docstring to get description, the tool name is the function name
tools = [FunctionTool.from_defaults(fn=get_current_time)]

async def main():
    load_dotenv()
    audio_handler = AudioHandler()
    input_handler = InputHandler()
    input_handler.loop = asyncio.get_running_loop()
    
    client = RealtimeClient(
        api_key=os.environ.get("OPENAI_API_KEY"),
        model=os.environ.get("OPENAI_MODEL"),
        on_text_delta=lambda text: print(f"\nAssistant: {text}", end="", flush=True),
        on_audio_delta=lambda audio: audio_handler.play_audio(audio),
        on_input_transcript=lambda transcript: print(f"\nYou said: {transcript}\nAssistant: ", end="", flush=True),
        on_output_transcript=lambda transcript: print(f"{transcript}", end="", flush=True),
        on_interrupt=lambda: audio_handler.stop_playback_immediately(),
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
        asyncio.create_task(audio_handler.start_streaming(client))
        
        # Simple input loop for quit command
        while True:
            command, _ = await input_handler.command_queue.get()
            
            if command == 'q':
                break
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        audio_handler.stop_streaming()
        audio_handler.cleanup()
        await client.close()

if __name__ == "__main__":
    print("Starting Realtime API CLI with Server VAD...")
    asyncio.run(main())
