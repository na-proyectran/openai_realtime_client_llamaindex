import asyncio
import os
from dotenv import load_dotenv

from pynput import keyboard
from openai_realtime_client import RealtimeClient, InputHandler, AudioHandler
from llama_index.core.tools import FunctionTool
from tools import get_current_time

# Add your own tools here!
# NOTE: FunctionTool parses the docstring to get description, the tool name is the function name
tools = [FunctionTool.from_defaults(fn=get_current_time)]

async def main():
    load_dotenv()
    # Initialize handlers
    audio_handler = AudioHandler()
    input_handler = InputHandler()
    input_handler.loop = asyncio.get_running_loop()
    
    # Initialize the realtime client
    client_args = dict(
        api_key=os.environ.get("OPENAI_API_KEY"),
        model=os.environ.get("OPENAI_MODEL"),
        on_text_delta=lambda text: print(f"\nAssistant: {text}", end="", flush=True),
        on_audio_delta=lambda audio: audio_handler.play_audio(audio),
        on_input_transcript=lambda transcript: print(f"\nYou said: {transcript}\nAssistant: ", end="", flush=True),
        on_output_transcript=lambda transcript: print(f"{transcript}", end="", flush=True),
        tools=tools,
    )
    
    # Start keyboard listener in a separate thread
    listener = keyboard.Listener(on_press=input_handler.on_press)
    listener.start()

    try:
        async with RealtimeClient(**client_args) as client:
            # Start message handling in the background
            asyncio.create_task(client.handle_messages())

            print("Connected to OpenAI Realtime API!")
            print("Commands:")
            print("- Type your message and press Enter to send text")
            print("- Press 'r' to start recording audio")
            print("- Press 'space' to stop recording")
            print("- Press 'q' to quit")
            print("")

            while True:
                # Wait for commands from the input handler
                command, data = await input_handler.command_queue.get()

                if command == 'q':
                    break
                elif command == 'r':
                    # Start recording
                    audio_handler.start_recording()
                elif command == 'space':
                    print("[About to stop recording]")
                    if audio_handler.recording:
                        # Stop recording and get audio data
                        audio_data = audio_handler.stop_recording()
                        print("[Recording stopped]")
                        if audio_data:
                            await client.send_audio(audio_data)
                            print("[Audio sent]")
                elif command == 'enter' and data:
                    # Send text message
                    await client.send_text(data)

                await asyncio.sleep(0.01)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        listener.stop()
        audio_handler.cleanup()

if __name__ == "__main__":
    # Install required packages:
    # pip install pyaudio pynput pydub websockets

    print("Starting Realtime API CLI...")
    asyncio.run(main())
