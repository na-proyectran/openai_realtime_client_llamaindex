import asyncio
import json
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from av.audio.frame import AudioFrame

from openai_realtime_client import RealtimeClient


class OutgoingAudioStreamTrack(MediaStreamTrack):
    """Audio track that pulls audio chunks from a queue."""

    kind = "audio"

    def __init__(self):
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def recv(self) -> AudioFrame:
        """Return next audio frame for the remote peer."""
        audio = await self._queue.get()
        frame = AudioFrame(format="s16", layout="mono", samples=len(audio) // 2)
        frame.planes[0].update(audio)
        frame.sample_rate = 24000
        return frame

    async def send_audio(self, audio: bytes) -> None:
        await self._queue.put(audio)


class RtcHandler:
    """Manage a WebRTC connection with a client and bridge audio to RealtimeClient."""

    def __init__(self):
        self.pc = RTCPeerConnection()
        self.outgoing = OutgoingAudioStreamTrack()
        self.pc.addTrack(self.outgoing)
        self.channel = None
        self._streaming_task = None

    async def create_answer(self, offer_sdp: str) -> str:
        """Handle SDP offer from client and return SDP answer."""
        @self.pc.on("datachannel")
        def on_datachannel(channel):
            self.channel = channel

        await self.pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp, type="offer"))
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        return self.pc.localDescription.sdp

    async def start_streaming(self, client: RealtimeClient) -> None:
        """Begin relaying incoming audio to the Realtime API."""

        @self.pc.on("track")
        def on_track(track):
            if track.kind == "audio":
                self._streaming_task = asyncio.create_task(self._relay_audio(track, client))

    async def _relay_audio(self, track: MediaStreamTrack, client: RealtimeClient) -> None:
        while True:
            try:
                frame = await track.recv()
                await client.stream_audio(frame.planes[0].to_bytes())
            except Exception:
                break

    async def stop_streaming(self) -> None:
        if self._streaming_task:
            self._streaming_task.cancel()
        await self.pc.close()

    async def send_audio(self, audio: bytes) -> None:
        await self.outgoing.send_audio(audio)

    async def send_clear_event(self) -> None:
        if self.channel and self.channel.readyState == "open":
            self.channel.send(json.dumps({"event": "clear"}))
