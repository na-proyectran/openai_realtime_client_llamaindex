let pc;
let stream;

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const muteBtn = document.getElementById('muteBtn');
const hal = document.querySelector('.animation');
hal.classList.add('idle');

startBtn.addEventListener('click', async () => {
    await startSession();
    startBtn.disabled = true;
    stopBtn.disabled = false;
    muteBtn.disabled = false;
});

stopBtn.addEventListener('click', () => {
    stopSession();
    startBtn.disabled = false;
    stopBtn.disabled = true;
    muteBtn.disabled = true;
    muteBtn.classList.remove('active');
});

muteBtn.addEventListener('click', () => {
    if (!stream) return;
    const track = stream.getAudioTracks()[0];
    track.enabled = !track.enabled;
    muteBtn.classList.toggle('active', !track.enabled);
});

async function startSession() {
    const resp = await fetch('/webrtc', {method: 'POST'});
    const data = await resp.json();
    const token = data?.client_secret?.value;

    pc = new RTCPeerConnection();

    // Play remote audio
    const remoteAudio = new Audio();
    remoteAudio.autoplay = true;
    pc.ontrack = (event) => {
        remoteAudio.srcObject = event.streams[0];
    };

    // Log events from data channel
    pc.ondatachannel = (event) => {
        event.channel.onmessage = e => console.log('Event:', e.data);
    };

    stream = await navigator.mediaDevices.getUserMedia({audio: true});
    stream.getTracks().forEach(track => pc.addTrack(track, stream));

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    const baseUrl = `https://api.openai.com/v1/realtime?model=${encodeURIComponent(data.model || '')}`;
    const ansResp = await fetch(baseUrl, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/sdp'
        },
        body: offer.sdp
    });
    const answer = await ansResp.text();
    await pc.setRemoteDescription({type: 'answer', sdp: answer});

    hal.classList.remove('idle');
    hal.classList.add('speaking');
}

function stopSession() {
    if (pc) {
        pc.close();
        pc = null;
    }
    if (stream) {
        stream.getTracks().forEach(t => t.stop());
        stream = null;
    }
    hal.classList.remove('speaking');
    hal.classList.add('idle');
}
