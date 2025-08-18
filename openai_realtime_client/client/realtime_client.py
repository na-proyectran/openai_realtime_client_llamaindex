import os
import asyncio
import websockets
import json
import base64
import io
import logging

from typing import Optional, Callable, List, Dict, Any
from enum import Enum
from pydub import AudioSegment
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    MediaStreamTrack,
)
from av.audio.frame import AudioFrame
import aiohttp

from llama_index.core.tools import BaseTool, AsyncBaseTool, ToolSelection, adapt_to_async_tool, call_tool_with_selection

logger = logging.getLogger(__name__)


def _convert_audio_bytes(audio_bytes: bytes) -> str:
    """Convert audio bytes to 24kHz mono PCM16 and return base64 string."""
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2)
    return base64.b64encode(audio.raw_data).decode()


class TurnDetectionMode(Enum):
    SERVER_VAD = "server_vad"
    SEMANTIC_VAD = "semantic_vad"
    MANUAL = "manual"


class ConnectionMode(Enum):
    WEBSOCKET = "websocket"
    WEBRTC = "webrtc"


class OutgoingAudioStreamTrack(MediaStreamTrack):
    """Audio track that pulls audio chunks from a queue."""

    kind = "audio"

    def __init__(self):
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def recv(self) -> AudioFrame:
        audio = await self._queue.get()
        frame = AudioFrame(format="s16", layout="mono", samples=len(audio) // 2)
        frame.planes[0].update(audio)
        frame.sample_rate = 24000
        return frame

    async def send_audio(self, audio: bytes) -> None:
        await self._queue.put(audio)

class RealtimeClient:
    """
    A client for interacting with the OpenAI Realtime API.

    This class provides methods to connect to the Realtime API, send text and audio data,
    handle responses, and manage the WebSocket connection.

    Attributes:
        api_key (str): 
            The API key for authentication.
        model (str): 
            The model to use for text and audio processing.
        voice (str): 
            The voice to use for audio output.
        instructions (str): 
            The instructions for the chatbot.
        temperature (float):
            The chatbot's temperature.
        turn_detection_mode (TurnDetectionMode): 
            The mode for turn detection.
        tools (List[BaseTool]): 
            The tools to use for function calling.
        on_text_delta (Callable[[str], None]): 
            Callback for text delta events. 
            Takes in a string and returns nothing.
        on_audio_delta (Callable[[bytes], None]): 
            Callback for audio delta events. 
            Takes in bytes and returns nothing.
        on_interrupt (Callable[[], None]): 
            Callback for user interrupt events, should be used to stop audio playback.
        on_input_transcript (Callable[[str], None]): 
            Callback for input transcript events. 
            Takes in a string and returns nothing.
        on_output_transcript (Callable[[str], None]): 
            Callback for output transcript events. 
            Takes in a string and returns nothing.
        extra_event_handlers (Dict[str, Callable[[Dict[str, Any]], None]]): 
            Additional event handlers. 
            Is a mapping of event names to functions that process the event payload.
    """
    def __init__(
        self, 
        api_key: str,
        model: str = os.environ.get(
            "OPENAI_MODEL", "gpt-4o-mini-realtime-preview-2024-12-17"
        ),
        voice: str = "alloy",
        instructions: str = "You are a helpful assistant",
        temperature: float = 0.8,
        language: str = "en",
        turn_detection_mode: TurnDetectionMode = TurnDetectionMode.MANUAL,
        connection_mode: ConnectionMode = ConnectionMode.WEBSOCKET,
        tools: Optional[List[BaseTool]] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_audio_delta: Optional[Callable[[bytes], None]] = None,
        on_interrupt: Optional[Callable[[], None]] = None,
        on_input_transcript: Optional[Callable[[str], None]] = None,  
        on_output_transcript: Optional[Callable[[str], None]] = None,  
        extra_event_handlers: Optional[Dict[str, Callable[[Dict[str, Any]], None]]] = None
    ):
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.ws = None
        self.on_text_delta = on_text_delta
        self.on_audio_delta = on_audio_delta
        self.on_interrupt = on_interrupt
        self.on_input_transcript = on_input_transcript
        self.on_output_transcript = on_output_transcript
        self.instructions = instructions
        self.temperature = temperature
        self.language = language
        self.connection_mode = connection_mode
        self.base_url = (
            "wss://api.openai.com/v1/realtime"
            if connection_mode == ConnectionMode.WEBSOCKET
            else "https://api.openai.com/v1/realtime"
        )
        self.extra_event_handlers = extra_event_handlers or {}
        self.turn_detection_mode = turn_detection_mode

        tools = tools or []
        for i, tool in enumerate(tools):
            tools[i] = adapt_to_async_tool(tool)
        self.tools: List[AsyncBaseTool] = tools

        # Track current response state
        self._current_response_id = None
        self._current_item_id = None
        self._is_responding = False
        # Track printing state for input and output transcripts
        self._print_input_transcript = False
        self._output_transcript_buffer = ""

        # WebRTC specific attributes
        self.pc: Optional[RTCPeerConnection] = None
        self.data_channel = None
        self.outgoing: Optional[OutgoingAudioStreamTrack] = None
        self._message_queue: Optional[asyncio.Queue[str]] = None
        self._dc_ready: Optional[asyncio.Event] = None

    async def _send_event(self, event: Dict[str, Any]) -> None:
        data = json.dumps(event)
        if self.connection_mode == ConnectionMode.WEBSOCKET:
            await self.ws.send(data)
        else:
            if self.data_channel and self.data_channel.readyState == "open":
                self.data_channel.send(data)

    async def connect(self) -> None:
        """Establish WebSocket connection with the Realtime API.

        Raises:
            RuntimeError: If the WebSocket connection fails.
        """
        if self.connection_mode == ConnectionMode.WEBSOCKET:
            url = f"{self.base_url}?model={self.model}"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }

            try:
                self.ws = await websockets.connect(url, additional_headers=headers)
            except (OSError, websockets.WebSocketException) as e:
                logger.exception("Failed to connect to the Realtime API")
                raise RuntimeError("Failed to establish connection to the Realtime API") from e
        else:
            self.pc = RTCPeerConnection()
            self.outgoing = OutgoingAudioStreamTrack()
            self.pc.addTrack(self.outgoing)
            self.data_channel = self.pc.createDataChannel("oai-events")
            self._message_queue = asyncio.Queue()
            self._dc_ready = asyncio.Event()

            @self.data_channel.on("open")
            def on_open():
                if self._dc_ready:
                    self._dc_ready.set()

            @self.data_channel.on("message")
            def on_message(message):
                if self._message_queue:
                    asyncio.create_task(self._message_queue.put(message))

            @self.pc.on("track")
            def on_track(track):
                if track.kind == "audio":
                    asyncio.create_task(self._handle_remote_audio(track))

            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}?model={self.model}",
                    data=offer.sdp,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/sdp",
                    },
                ) as resp:
                    answer_sdp = await resp.text()

            await self.pc.setRemoteDescription(
                RTCSessionDescription(sdp=answer_sdp, type="answer")
            )

            if self._dc_ready:
                await self._dc_ready.wait()

        # Set up default session configuration
        tools = [t.metadata.to_openai_tool()['function'] for t in self.tools]
        for t in tools:
            t['type'] = 'function'  # TODO: OpenAI docs didn't say this was needed, but it was

        if self.turn_detection_mode == TurnDetectionMode.MANUAL:
            await self.update_session({
                "modalities": ["text", "audio"],
                "instructions": self.instructions,
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "input_audio_noise_reduction": {
                    "type": "far_field"
                },
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "gpt-4o-mini-transcribe",
                    "language": self.language,
                },
                "tools": tools,
                "tool_choice": "auto",
                "temperature": self.temperature,
            })
        elif self.turn_detection_mode == TurnDetectionMode.SERVER_VAD:
            await self.update_session({
                "modalities": ["text", "audio"],
                "instructions": self.instructions,
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "input_audio_noise_reduction": {
                    "type": "far_field"
                },
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "gpt-4o-mini-transcribe",
                    "language": self.language,
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 500,
                    "silence_duration_ms": 200,
                    "create_response": True,
                    "interrupt_response": True,
                },
                "tools": tools,
                "tool_choice": "auto",
                "temperature": self.temperature,
            })
        elif self.turn_detection_mode == TurnDetectionMode.SEMANTIC_VAD:
            await self.update_session({
                "modalities": ["text", "audio"],
                "instructions": self.instructions,
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "input_audio_noise_reduction": {
                    "type": "far_field"
                },
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "gpt-4o-mini-transcribe",
                    "language": self.language,
                },
                "turn_detection": {
                    "type": "semantic_vad",
                    "eagerness": "auto",
                    "create_response": True,
                    "interrupt_response": True,
                },
                "tools": tools,
                "tool_choice": "auto",
                "temperature": self.temperature,
            })
        else:
            raise ValueError(f"Invalid turn detection mode: {self.turn_detection_mode}")

    async def update_session(self, config: Dict[str, Any]) -> None:
        """Update session configuration."""
        event = {
            "type": "session.update",
            "session": config
        }
        await self._send_event(event)

    async def send_text(self, text: str) -> None:
        """Send text message to the API."""
        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": text
                }]
            }
        }
        await self._send_event(event)
        await self.create_response()

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Send audio data to the API."""
        # Convert audio to required format (24kHz, mono, PCM16)
        pcm_b64 = await asyncio.to_thread(_convert_audio_bytes, audio_bytes)

        if self.connection_mode == ConnectionMode.WEBSOCKET:
            append_event = {
                "type": "input_audio_buffer.append",
                "audio": pcm_b64
            }
            await self._send_event(append_event)

            commit_event = {
                "type": "input_audio_buffer.commit"
            }
            await self._send_event(commit_event)
        else:
            if self.outgoing:
                await self.outgoing.send_audio(base64.b64decode(pcm_b64))

        if self.turn_detection_mode == TurnDetectionMode.MANUAL:
            await self.create_response()

    async def stream_audio(self, audio_chunk: bytes) -> None:
        """Stream raw audio data to the API."""
        if self.connection_mode == ConnectionMode.WEBSOCKET:
            audio_b64 = base64.b64encode(audio_chunk).decode()
            append_event = {
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }
            await self._send_event(append_event)
        else:
            if self.outgoing:
                await self.outgoing.send_audio(audio_chunk)

    async def create_response(self, functions: Optional[List[Dict[str, Any]]] = None) -> None:
        """Request a response from the API. Needed when using manual mode."""
        event = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"]
            }
        }
        if functions:
            event["response"]["tools"] = functions # type: ignore
        await self._send_event(event)

    async def send_function_result(self, call_id: str, result: Any) -> None:
        """Send function call result back to the API."""
        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result
            }
        }
        await self._send_event(event)

        # functions need a manual response
        await self.create_response()

    async def cancel_response(self) -> None:
        """Cancel the current response."""
        event = {
            "type": "response.cancel"
        }
        await self._send_event(event)
    
    async def truncate_response(self):
        """Truncate the conversation item to match what was actually played."""
        if self._current_item_id:
            event = {
                "type": "conversation.item.truncate",
                "item_id": self._current_item_id
            }
            await self._send_event(event)

    async def call_tool(self, call_id: str,tool_name: str, tool_arguments: Dict[str, Any]) -> None:
        tool_selection = ToolSelection(
            tool_id="tool_id",
            tool_name=tool_name,
            tool_kwargs=tool_arguments
        )

        # avoid blocking the event loop with sync tools
        # by using asyncio.to_thread
        tool_result = await asyncio.to_thread(
            call_tool_with_selection,
            tool_selection, 
            self.tools, 
            verbose=True
        )
        await self.send_function_result(call_id, str(tool_result))

    async def handle_interruption(self):
        """Handle user interruption of the current response."""
        if not self._is_responding:
            return
            
        print("\n[Handling interruption]")
        
        # 1. Cancel the current response
        if self._current_response_id:
            await self.cancel_response()
        
        # 2. Truncate the conversation item to what was actually played
        if self._current_item_id:
            await self.truncate_response()
            
        self._is_responding = False
        self._current_response_id = None
        self._current_item_id = None

    async def _process_event(self, message: str) -> None:
        event = json.loads(message)
        event_type = event.get("type")

        if event_type == "error":
            print(f"Error: {event['error']}")
            return

        # Track response state
        if event_type == "response.created":
            self._current_response_id = event.get("response", {}).get("id")
            self._is_responding = True

        elif event_type == "response.output_item.added":
            self._current_item_id = event.get("item", {}).get("id")

        elif event_type == "response.done":
            self._is_responding = False
            self._current_response_id = None
            self._current_item_id = None

        # Handle interruptions
        elif event_type == "input_audio_buffer.speech_started":
            print("\n[Speech detected]")
            if self._is_responding:
                await self.handle_interruption()

            if self.on_interrupt:
                self.on_interrupt()

        elif event_type == "input_audio_buffer.speech_stopped":
            print("\n[Speech ended]")

        # Handle normal response events
        elif event_type == "response.text.delta":
            if self.on_text_delta:
                self.on_text_delta(event["delta"])

        elif event_type == "response.audio.delta":
            if self.on_audio_delta:
                audio_bytes = base64.b64decode(event["delta"])
                self.on_audio_delta(audio_bytes)

        elif event_type == "response.function_call_arguments.done":
            await self.call_tool(event["call_id"], event['name'], json.loads(event['arguments']))

        # Handle input audio transcription
        elif event_type == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "")

            if self.on_input_transcript:
                await asyncio.to_thread(self.on_input_transcript, transcript)
                self._print_input_transcript = True

        # Handle output audio transcription
        elif event_type == "response.audio_transcript.delta":
            if self.on_output_transcript:
                delta = event.get("delta", "")
                if not self._print_input_transcript:
                    self._output_transcript_buffer += delta
                else:
                    if self._output_transcript_buffer:
                        await asyncio.to_thread(
                            self.on_output_transcript, self._output_transcript_buffer
                        )
                        self._output_transcript_buffer = ""
                    await asyncio.to_thread(self.on_output_transcript, delta)

        elif event_type == "response.audio_transcript.done":
            self._print_input_transcript = False

        elif event_type in self.extra_event_handlers:
            self.extra_event_handlers[event_type](event)

    async def handle_messages(self) -> None:
        try:
            if self.connection_mode == ConnectionMode.WEBSOCKET:
                async for message in self.ws:
                    await self._process_event(message)
            else:
                while True:
                    if self._message_queue is None:
                        break
                    message = await self._message_queue.get()
                    await self._process_event(message)
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")
        except Exception as e:
            print(f"Error in message handling: {str(e)}")

    async def _handle_remote_audio(self, track: MediaStreamTrack) -> None:
        while True:
            try:
                frame = await track.recv()
                if self.on_audio_delta:
                    self.on_audio_delta(frame.planes[0].to_bytes())
            except Exception:
                break

    async def close(self) -> None:
        """Close the active connection."""
        if self.connection_mode == ConnectionMode.WEBSOCKET:
            if self.ws:
                await self.ws.close()
        else:
            if self.pc:
                await self.pc.close()
