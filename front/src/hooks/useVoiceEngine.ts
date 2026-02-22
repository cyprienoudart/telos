"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { AudioPlayerQueue } from "@/utils/audioPlayer";

export type VoiceMode = "idle" | "listening" | "loading" | "speaking";

interface UseVoiceEngineReturn {
    mode: VoiceMode;
    audioLevel: number;
    isActive: boolean;
    transcript: string;
    startConversation: () => Promise<void>;
    stopConversation: () => void;
}

/**
 * @param onTranscriptCommit Called when the user finishes speaking.
 *   Receives the transcript text, should return the AI response text to TTS
 *   (or null to skip TTS).
 */
export function useVoiceEngine(
    onTranscriptCommit?: (text: string) => Promise<string | null>,
): UseVoiceEngineReturn {
    const [mode, setMode] = useState<VoiceMode>("idle");
    const [audioLevel, setAudioLevel] = useState(0);
    const [isActive, setIsActive] = useState(false);
    const [transcript, setTranscript] = useState("");

    const mediaStreamRef = useRef<MediaStream | null>(null);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioPlayerRef = useRef<AudioPlayerQueue | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const micContextRef = useRef<AudioContext | null>(null);
    const animFrameRef = useRef(0);
    const scribeWsRef = useRef<WebSocket | null>(null);
    const isActiveRef = useRef(false);
    const ttsAbortRef = useRef<AbortController | null>(null);
    const onTranscriptCommitRef = useRef(onTranscriptCommit);

    // Keep callback ref fresh
    useEffect(() => {
        onTranscriptCommitRef.current = onTranscriptCommit;
    }, [onTranscriptCommit]);

    // Clean up on unmount
    useEffect(() => {
        return () => {
            stopConversation();
        };
    }, []);

    const monitorMicLevel = useCallback(() => {
        if (!analyserRef.current || !isActiveRef.current) return;
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);

        const measure = () => {
            if (!isActiveRef.current || !analyserRef.current) return;
            analyserRef.current.getByteFrequencyData(dataArray);
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i] * dataArray[i];
            }
            const rms = Math.sqrt(sum / dataArray.length) / 255;
            setAudioLevel(Math.min(1, rms * 3));
            animFrameRef.current = requestAnimationFrame(measure);
        };
        animFrameRef.current = requestAnimationFrame(measure);
    }, []);

    const handleCommittedTranscript = useCallback(async (text: string) => {
        if (!text.trim()) return;

        setTranscript(text);
        setMode("loading");
        setAudioLevel(0);

        // Stop mic recording during processing
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
            mediaRecorderRef.current.pause();
        }

        // Route transcript through backend via callback, get AI response
        let ttsText = text; // fallback: TTS the user's own text
        if (onTranscriptCommitRef.current) {
            try {
                const aiResponse = await onTranscriptCommitRef.current(text);
                if (aiResponse) {
                    ttsText = aiResponse;
                } else {
                    // No response to speak (e.g. conversation done, build started)
                    resumeMicMonitoring();
                    return;
                }
            } catch {
                console.error("Transcript commit callback failed");
                resumeMicMonitoring();
                return;
            }
        }

        // Request TTS of the AI response
        try {
            const abortController = new AbortController();
            ttsAbortRef.current = abortController;

            const response = await fetch("/api/tts-stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: ttsText }),
                signal: abortController.signal,
            });

            if (!response.ok || !response.body) {
                console.error("TTS stream failed:", response.status);
                setMode("listening");
                resumeMicMonitoring();
                return;
            }

            setMode("speaking");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Parse SSE events
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const payload = line.slice(6).trim();
                        if (payload === "[DONE]") {
                            break;
                        }
                        try {
                            const parsed = JSON.parse(payload);
                            if (parsed.audio) {
                                audioPlayerRef.current?.enqueue(parsed.audio);
                            }
                        } catch {
                            // Ignore parse errors
                        }
                    }
                }
            }
        } catch (err: unknown) {
            if (err instanceof Error && err.name === "AbortError") {
                console.log("TTS streaming aborted (interruption)");
            } else {
                console.error("TTS error:", err);
            }
        }

        ttsAbortRef.current = null;
    }, []);

    const resumeMicMonitoring = useCallback(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === "paused") {
            mediaRecorderRef.current.resume();
        }
        setMode("listening");
        monitorMicLevel();
    }, [monitorMicLevel]);

    const handleInterruption = useCallback(() => {
        // User started speaking while AI is responding — interrupt
        if (audioPlayerRef.current?.getIsPlaying()) {
            console.log("User interrupted — clearing TTS queue");
            audioPlayerRef.current.clearQueue();

            // Abort the TTS stream
            if (ttsAbortRef.current) {
                ttsAbortRef.current.abort();
                ttsAbortRef.current = null;
            }

            setMode("listening");
        }
    }, []);

    const startConversation = useCallback(async () => {
        try {
            // 1. Request mic permission
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaStreamRef.current = stream;

            // 2. Set up mic analyser for audio level
            const micCtx = new AudioContext();
            micContextRef.current = micCtx;
            const source = micCtx.createMediaStreamSource(stream);
            const analyser = micCtx.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            analyserRef.current = analyser;

            // 3. Set up audio player for TTS output
            audioPlayerRef.current = new AudioPlayerQueue({
                onAmplitudeChange: (level) => setAudioLevel(level),
                onPlaybackEnd: () => {
                    if (isActiveRef.current) {
                        resumeMicMonitoring();
                    }
                },
            });

            // 4. Fetch scribe token
            let scribeToken: string | null = null;
            try {
                const tokenRes = await fetch("/api/scribe-token");
                if (tokenRes.ok) {
                    const tokenData = await tokenRes.json();
                    scribeToken = tokenData.token;
                }
            } catch (e) {
                console.warn("Could not fetch scribe token, using local recording:", e);
            }

            // 5. Set up real-time transcription via ElevenLabs Scribe WebSocket
            if (scribeToken) {
                try {
                    const ws = new WebSocket(
                        `wss://api.elevenlabs.io/v1/speech-to-text/realtime?token=${scribeToken}&model_id=scribe_v2_realtime&language=en`
                    );
                    scribeWsRef.current = ws;

                    ws.onopen = () => {
                        console.log("Scribe WebSocket connected");
                        // Start sending audio data
                        const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
                        mediaRecorderRef.current = recorder;

                        recorder.ondataavailable = async (e) => {
                            if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
                                const arrayBuffer = await e.data.arrayBuffer();
                                ws.send(arrayBuffer);
                            }
                        };

                        recorder.start(250); // Send chunks every 250ms
                    };

                    ws.onmessage = (event) => {
                        try {
                            const data = JSON.parse(event.data);

                            if (data.type === "transcript" && data.is_partial === false && data.text) {
                                console.log("Committed transcript:", data.text);
                                handleCommittedTranscript(data.text);
                            } else if (data.type === "transcript" && data.is_partial === true && data.text) {
                                console.log("Partial:", data.text);
                                // If partial transcript comes in while speaking → interrupt
                                if (audioPlayerRef.current?.getIsPlaying()) {
                                    handleInterruption();
                                }
                            }
                        } catch {
                            // Ignore
                        }
                    };

                    ws.onerror = (e) => {
                        console.error("Scribe WebSocket error:", e);
                    };

                    ws.onclose = () => {
                        console.log("Scribe WebSocket closed");
                    };
                } catch (e) {
                    console.warn("Scribe WebSocket setup failed:", e);
                }
            }

            // If Scribe WS failed, fall back to local MediaRecorder + manual send
            if (!scribeWsRef.current || scribeWsRef.current.readyState !== WebSocket.CONNECTING) {
                if (!mediaRecorderRef.current) {
                    const recorder = new MediaRecorder(stream);
                    mediaRecorderRef.current = recorder;

                    const chunks: Blob[] = [];
                    recorder.ondataavailable = (e) => {
                        if (e.data.size > 0) chunks.push(e.data);
                    };
                    recorder.onstop = () => {
                        const audioBlob = new Blob(chunks, { type: "audio/webm" });
                        console.log("Local recording:", audioBlob.size, "bytes (fallback mode)");
                    };
                    recorder.start(250);
                }
            }

            isActiveRef.current = true;
            setIsActive(true);
            setMode("listening");
            monitorMicLevel();
        } catch (err) {
            console.error("Failed to start conversation:", err);
        }
    }, [monitorMicLevel, handleCommittedTranscript, handleInterruption, resumeMicMonitoring]);

    const stopConversation = useCallback(() => {
        isActiveRef.current = false;
        setIsActive(false);
        setMode("idle");
        setAudioLevel(0);
        cancelAnimationFrame(animFrameRef.current);

        // Stop scribe WS
        if (scribeWsRef.current) {
            scribeWsRef.current.close();
            scribeWsRef.current = null;
        }

        // Stop media recorder
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
            mediaRecorderRef.current.stop();
        }
        mediaRecorderRef.current = null;

        // Stop mic stream
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach((t) => t.stop());
            mediaStreamRef.current = null;
        }

        // Close mic audio context
        if (micContextRef.current) {
            micContextRef.current.close();
            micContextRef.current = null;
        }

        // Abort TTS
        if (ttsAbortRef.current) {
            ttsAbortRef.current.abort();
            ttsAbortRef.current = null;
        }

        // Clear audio player
        if (audioPlayerRef.current) {
            audioPlayerRef.current.destroy();
            audioPlayerRef.current = null;
        }
    }, []);

    return {
        mode,
        audioLevel,
        isActive,
        transcript,
        startConversation,
        stopConversation,
    };
}
