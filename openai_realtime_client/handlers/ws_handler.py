import asyncio
from fastapi import WebSocket

from openai_realtime_client import RealtimeClient

class WsHandler:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        # streaming params
        self.streaming = False


    async def start_streaming(self, client: RealtimeClient):
        """Start continuous audio streaming."""
        if self.streaming:
            return

        self.streaming = True
        print("\nStreaming audio... Press 'q' to stop.")

        while self.streaming:
            try:
                # Read raw PCM data
                async for data in self.ws.iter_bytes():
                    # Stream directly without trying to decode
                    await client.stream_audio(data)
            except Exception as e:
                print(f"Error streaming: {e}")
                break
            await asyncio.sleep(0.01)


    def stop_streaming(self):
        """Stop audio streaming."""
        self.streaming = False
        if self.ws:
            self.ws.close()
