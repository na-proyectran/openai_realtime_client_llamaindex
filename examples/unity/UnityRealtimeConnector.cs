using UnityEngine;
using WebSocketSharp;
using System;

public class UnityRealtimeConnector : MonoBehaviour
{
    [Header("WebSocket settings")]
    public string serverUrl = "ws://localhost:8000/ws";
    public AudioSource audioSource;

    private WebSocket ws;
    private AudioClip micClip;
    private int lastSample = 0;

    void Start()
    {
        // Connect to the Python WebSocket server
        ws = new WebSocket(serverUrl);
        ws.OnMessage += OnMessage;
        ws.Connect();

        // Begin recording from the default microphone
        micClip = Microphone.Start(null, true, 1, 16000);

        // Send audio chunks every 100ms
        InvokeRepeating(nameof(SendMicData), 0.1f, 0.1f);
    }

    void SendMicData()
    {
        if (micClip == null || ws == null || ws.ReadyState != WebSocketState.Open)
            return;

        int pos = Microphone.GetPosition(null);
        int diff = pos - lastSample;
        if (diff <= 0)
            return;

        float[] samples = new float[diff * micClip.channels];
        micClip.GetData(samples, lastSample);
        byte[] bytes = FloatArrayToPCM16(samples);

        ws.Send(bytes);
        lastSample = pos;
    }

    byte[] FloatArrayToPCM16(float[] samples)
    {
        byte[] bytes = new byte[samples.Length * 2];
        for (int i = 0; i < samples.Length; i++)
        {
            short val = (short)(Mathf.Clamp(samples[i], -1f, 1f) * short.MaxValue);
            byte[] byteArr = BitConverter.GetBytes(val);
            bytes[i * 2] = byteArr[0];
            bytes[i * 2 + 1] = byteArr[1];
        }
        return bytes;
    }

    void OnMessage(object sender, MessageEventArgs e)
    {
        if (!e.IsText)
            return;

        Payload payload = JsonUtility.FromJson<Payload>(e.Data);
        if (!string.IsNullOrEmpty(payload.audio))
        {
            byte[] audioBytes = Convert.FromBase64String(payload.audio);
            PlayAudio(audioBytes);
        }
    }

    void PlayAudio(byte[] audioBytes)
    {
        int sampleCount = audioBytes.Length / 2;
        float[] samples = new float[sampleCount];
        for (int i = 0; i < sampleCount; i++)
        {
            short sample = BitConverter.ToInt16(audioBytes, i * 2);
            samples[i] = sample / 32768f;
        }

        AudioClip clip = AudioClip.Create("assistant", sampleCount, 1, 24000, false);
        clip.SetData(samples, 0);
        audioSource.clip = clip;
        audioSource.Play();
    }

    [Serializable]
    public class Payload
    {
        public string audio;
    }

    void OnDestroy()
    {
        if (ws != null)
            ws.Close();
        Microphone.End(null);
    }
}
