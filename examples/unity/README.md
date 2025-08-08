# Unity Realtime Connector

This example shows how to connect a Unity NPC avatar with the Python OpenAI Realtime client.
It streams microphone audio from Unity to the model and plays back the generated audio response.

## Python WebSocket server

1. Install dependencies and set your OpenAI key in a `.env` file (see project README).
2. Start the server:

```bash
pip install fastapi uvicorn websockets python-dotenv
python examples/unity_ws_server.py
```

   You can also run the server inside Docker using the instructions in the
   project root README or start it alongside the monitoring stack with
   `docker compose up`.

The server exposes a WebSocket endpoint at `ws://localhost:8000/ws` that accepts raw PCM16 audio
and returns base64 encoded audio chunks from the assistant.

## Unity setup

1. Import the [`UnityRealtimeConnector.cs`](UnityRealtimeConnector.cs) script into your project.
2. Add the [`websocket-sharp`](https://github.com/sta/websocket-sharp) library to enable WebSocket support.
3. Create a GameObject and attach `UnityRealtimeConnector`.
4. Assign an `AudioSource` component on the same object to play the assistant's voice.
5. Ensure that microphone permission is granted and run the scene. The NPC will speak using the
assistant's response and the microphone input is streamed to the model.

## Notes

- Audio is sent and received as 16‑bit PCM. The server converts output to 24 kHz mono before playback.
- Modify `serverUrl` in the script if the Python server runs on another host/port.
