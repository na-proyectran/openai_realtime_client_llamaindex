import asyncio
from fastapi import WebSocket

from openai_realtime_client import RealtimeClient
import base64
import json
from starlette.websockets import WebSocketState

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

    async def send_audio(self, audio: bytes) -> None:
        """Send base64 encoded audio over the websocket."""
        if self.ws.application_state == WebSocketState.CONNECTED:
            payload = {
                "audio": base64.b64encode(audio).decode()
            }
            await self.ws.send_text(json.dumps(payload))

    async def send_clear_event(self) -> None:
        """Notify the client to stop audio playback."""
        if self.ws.application_state == WebSocketState.CONNECTED:
            await self.ws.send_text(json.dumps({"event": "clear"}))
