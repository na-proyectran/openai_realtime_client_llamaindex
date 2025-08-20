class RealtimeDemo {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.isMuted = false;
        this.isCapturing = false;
        this.audioContext = null;
        this.processor = null;
        this.stream = null;
        this.sessionId = this.generateSessionId();

        // Audio playback state
        this.playbackAudioContext = null;
        this.nextPlaybackTime = 0;
        this.activeSources = [];
        
        this.initializeElements();
        this.setupEventListeners();
    }
    
    initializeElements() {
        this.connectBtn = document.getElementById('connectBtn');
        this.muteBtn = document.getElementById('muteBtn');
        this.status = document.getElementById('status');
        this.messagesContent = document.getElementById('messagesContent');
        this.eventsContent = document.getElementById('eventsContent');
        this.toolsContent = document.getElementById('toolsContent');
    }
    
    setupEventListeners() {
        this.connectBtn.addEventListener('click', () => {
            if (this.isConnected) {
                this.disconnect();
            } else {
                this.connect();
            }
        });
        
        this.muteBtn.addEventListener('click', () => {
            this.toggleMute();
        });
    }
    
    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9);
    }
    
    async connect() {
        try {
            this.ws = new WebSocket(`ws://localhost:8000/ws/${this.sessionId}`);
            
            this.ws.onopen = () => {
                this.isConnected = true;
                this.updateConnectionUI();
                this.startContinuousCapture();
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleRealtimeEvent(data);
            };
            
            this.ws.onclose = () => {
                this.isConnected = false;
                this.updateConnectionUI();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
        } catch (error) {
            console.error('Failed to connect:', error);
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
        this.stopContinuousCapture();
    }
    
    updateConnectionUI() {
        if (this.isConnected) {
            this.connectBtn.textContent = 'Disconnect';
            this.connectBtn.className = 'connect-btn connected';
            this.status.textContent = 'Connected';
            this.status.className = 'status connected';
            this.muteBtn.disabled = false;
        } else {
            this.connectBtn.textContent = 'Connect';
            this.connectBtn.className = 'connect-btn disconnected';
            this.status.textContent = 'Disconnected';
            this.status.className = 'status disconnected';
            this.muteBtn.disabled = true;
        }
    }
    
    toggleMute() {
        this.isMuted = !this.isMuted;
        this.updateMuteUI();
    }
    
    updateMuteUI() {
        if (this.isMuted) {
            this.muteBtn.textContent = '🔇 Mic Off';
            this.muteBtn.className = 'mute-btn muted';
        } else {
            this.muteBtn.textContent = '🎤 Mic On';
            this.muteBtn.className = 'mute-btn unmuted';
            if (this.isCapturing) {
                this.muteBtn.classList.add('active');
            }
        }
    }
    
    async startContinuousCapture() {
        if (!this.isConnected || this.isCapturing) return;
        
        // Check if getUserMedia is available
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('getUserMedia not available. Please use HTTPS or localhost.');
        }
        
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.audioContext = new AudioContext({ sampleRate: 24000 });
            const source = this.audioContext.createMediaStreamSource(this.stream);

            if (this.audioContext.audioWorklet) {
                await this.audioContext.audioWorklet.addModule('worklet.js');
                this.processor = new AudioWorkletNode(this.audioContext, 'capture-processor');
                this.processor.port.onmessage = (e) => {
                    if (!this.isMuted && this.ws && this.ws.readyState === WebSocket.OPEN) {
                        const pcm16 = e.data;
                        this.ws.send(JSON.stringify({
                            type: 'audio',
                            data: Array.from(pcm16)
                        }));
                    }
                };
            } else {
                // Fallback for browsers without AudioWorklet support
                this.processor = this.audioContext.createScriptProcessor(1024, 1, 1);
                this.processor.onaudioprocess = (event) => {
                    if (!this.isMuted && this.ws && this.ws.readyState === WebSocket.OPEN) {
                        const input = event.inputBuffer.getChannelData(0);
                        const pcm16 = new Int16Array(input.length);
                        for (let i = 0; i < input.length; i++) {
                            let s = Math.max(-1, Math.min(1, input[i]));
                            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                        }
                        this.ws.send(JSON.stringify({
                            type: 'audio',
                            data: Array.from(pcm16)
                        }));
                    }
                };
            }

            source.connect(this.processor);
            this.processor.connect(this.audioContext.destination);

            this.isCapturing = true;
            this.updateMuteUI();
        } catch (error) {
            console.error('Failed to start audio capture:', error);
        }
    }
    
    stopContinuousCapture() {
        if (!this.isCapturing) return;
        
        this.isCapturing = false;
        
        if (this.processor) {
            this.processor.disconnect();
            this.processor = null;
        }
        
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        this.updateMuteUI();
    }
    
    handleRealtimeEvent(event) {
        // Add to raw events pane
        this.addRawEvent(event);
        
        // Add to tools panel if it's a tool or handoff event
        if (event.type === 'tool_start' || event.type === 'tool_end' || event.type === 'handoff') {
            this.addToolEvent(event);
        }
        
        // Handle specific event types
        switch (event.type) {
            case 'audio':
                this.playAudio(event.audio);
                break;
            case 'audio_interrupted':
                this.stopAudioPlayback();
                break;
            case 'history_updated':
                this.updateMessagesFromHistory(event.history);
                break;
        }
    }
    
    
    updateMessagesFromHistory(history) {
        console.log('updateMessagesFromHistory called with:', history);
        
        // Clear all existing messages
        this.messagesContent.innerHTML = '';
        
        // Add messages from history
        if (history && Array.isArray(history)) {
            console.log('Processing history array with', history.length, 'items');
            history.forEach((item, index) => {
                console.log(`History item ${index}:`, item);
                if (item.type === 'message') {
                    const role = item.role;
                    let content = '';
                    
                    console.log(`Message item - role: ${role}, content:`, item.content);
                    
                    if (item.content && Array.isArray(item.content)) {
                        // Extract text from content array
                        item.content.forEach(contentPart => {
                            console.log('Content part:', contentPart);
                            if (contentPart.type === 'text' && contentPart.text) {
                                content += contentPart.text;
                            } else if (contentPart.type === 'input_text' && contentPart.text) {
                                content += contentPart.text;
                            } else if (contentPart.type === 'input_audio' && contentPart.transcript) {
                                content += contentPart.transcript;
                            } else if (contentPart.type === 'audio' && contentPart.transcript) {
                                content += contentPart.transcript;
                            }
                        });
                    }
                    
                    console.log(`Final content for ${role}:`, content);
                    
                    if (content.trim()) {
                        this.addMessage(role, content.trim());
                        console.log(`Added message: ${role} - ${content.trim()}`);
                    }
                } else {
                    console.log(`Skipping non-message item of type: ${item.type}`);
                }
            });
        } else {
            console.log('History is not an array or is null/undefined');
        }
        
        this.scrollToBottom();
    }
    
    addMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        bubbleDiv.textContent = content;
        
        messageDiv.appendChild(bubbleDiv);
        this.messagesContent.appendChild(messageDiv);
        this.scrollToBottom();
        
        return messageDiv;
    }
    
    addRawEvent(event) {
        const eventDiv = document.createElement('div');
        eventDiv.className = 'event';
        
        const headerDiv = document.createElement('div');
        headerDiv.className = 'event-header';
        headerDiv.innerHTML = `
            <span>${event.type}</span>
            <span>▼</span>
        `;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'event-content collapsed';
        contentDiv.textContent = JSON.stringify(event, null, 2);
        
        headerDiv.addEventListener('click', () => {
            const isCollapsed = contentDiv.classList.contains('collapsed');
            contentDiv.classList.toggle('collapsed');
            headerDiv.querySelector('span:last-child').textContent = isCollapsed ? '▲' : '▼';
        });
        
        eventDiv.appendChild(headerDiv);
        eventDiv.appendChild(contentDiv);
        this.eventsContent.appendChild(eventDiv);
        
        // Auto-scroll events pane
        this.eventsContent.scrollTop = this.eventsContent.scrollHeight;
    }
    
    addToolEvent(event) {
        const eventDiv = document.createElement('div');
        eventDiv.className = 'event';
        
        let title = '';
        let description = '';
        let eventClass = '';
        
        if (event.type === 'handoff') {
            title = `🔄 Handoff`;
            description = `From ${event.from} to ${event.to}`;
            eventClass = 'handoff';
        } else if (event.type === 'tool_start') {
            title = `🔧 Tool Started`;
            description = `Running ${event.tool}`;
            eventClass = 'tool';
        } else if (event.type === 'tool_end') {
            title = `✅ Tool Completed`;
            description = `${event.tool}: ${event.output || 'No output'}`;
            eventClass = 'tool';
        }
        
        eventDiv.innerHTML = `
            <div class="event-header ${eventClass}">
                <div>
                    <div style="font-weight: 600; margin-bottom: 2px;">${title}</div>
                    <div style="font-size: 0.8rem; opacity: 0.8;">${description}</div>
                </div>
                <span style="font-size: 0.7rem; opacity: 0.6;">${new Date().toLocaleTimeString()}</span>
            </div>
        `;
        
        this.toolsContent.appendChild(eventDiv);
        
        // Auto-scroll tools pane
        this.toolsContent.scrollTop = this.toolsContent.scrollHeight;
    }
    
    async playAudio(audioBase64) {
        try {
            if (!audioBase64 || audioBase64.length === 0) {
                console.warn('Received empty audio data, skipping playback');
                return;
            }

            if (!this.playbackAudioContext) {
                this.playbackAudioContext = new AudioContext({ sampleRate: 24000 });
                this.nextPlaybackTime = this.playbackAudioContext.currentTime;
            }

            // Decode base64 to bytes
            const binaryString = atob(audioBase64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            const int16Array = new Int16Array(bytes.buffer);
            if (int16Array.length === 0) {
                console.warn('Audio chunk has no samples, skipping');
                return;
            }

            const float32Array = new Float32Array(int16Array.length);
            for (let i = 0; i < int16Array.length; i++) {
                float32Array[i] = int16Array[i] / 32768.0;
            }

            const audioBuffer = this.playbackAudioContext.createBuffer(1, float32Array.length, 24000);
            audioBuffer.getChannelData(0).set(float32Array);

            const source = this.playbackAudioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.playbackAudioContext.destination);

            if (this.nextPlaybackTime < this.playbackAudioContext.currentTime) {
                this.nextPlaybackTime = this.playbackAudioContext.currentTime;
            }

            source.start(this.nextPlaybackTime);
            this.activeSources.push(source);
            source.onended = () => {
                this.activeSources = this.activeSources.filter(s => s !== source);
            };
            this.nextPlaybackTime += audioBuffer.duration;

        } catch (error) {
            console.error('Failed to play audio:', error);
        }
    }

    stopAudioPlayback() {
        if (this.activeSources.length > 0) {
            this.activeSources.forEach(src => {
                try { src.stop(); } catch (e) {}
            });
            this.activeSources = [];
        }
        if (this.playbackAudioContext) {
            this.nextPlaybackTime = this.playbackAudioContext.currentTime;
        } else {
            this.nextPlaybackTime = 0;
        }
    }
    
    scrollToBottom() {
        this.messagesContent.scrollTop = this.messagesContent.scrollHeight;
    }
}

// Initialize the demo when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new RealtimeDemo();
});