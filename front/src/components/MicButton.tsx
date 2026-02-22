"use client";

import { useState, useCallback, useRef } from "react";

interface MicButtonProps {
    onTranscript?: (text: string) => void;
    onListeningChange?: (isListening: boolean) => void;
}

export default function MicButton({ onTranscript, onListeningChange }: MicButtonProps) {
    const [listening, setListening] = useState(false);
    const [permissionDenied, setPermissionDenied] = useState(false);
    const mediaStreamRef = useRef<MediaStream | null>(null);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);

    const startListening = useCallback(async () => {
        try {
            // Request microphone permission
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaStreamRef.current = stream;

            // Create MediaRecorder for future ElevenLabs integration
            const recorder = new MediaRecorder(stream);
            mediaRecorderRef.current = recorder;

            const chunks: Blob[] = [];
            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) chunks.push(e.data);
            };

            recorder.onstop = () => {
                // This audio blob will be sent to ElevenLabs later
                const audioBlob = new Blob(chunks, { type: "audio/webm" });
                console.log("Audio recorded:", audioBlob.size, "bytes — ready for ElevenLabs");

                // For now, provide a placeholder transcript
                if (onTranscript) {
                    onTranscript("[Voice input — ElevenLabs integration pending]");
                }
            };

            recorder.start();
            setListening(true);
            setPermissionDenied(false);
            onListeningChange?.(true);
        } catch (err) {
            console.error("Microphone access denied:", err);
            setPermissionDenied(true);
        }
    }, [onTranscript, onListeningChange]);

    const stopListening = useCallback(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
            mediaRecorderRef.current.stop();
        }
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach((t) => t.stop());
            mediaStreamRef.current = null;
        }
        setListening(false);
        onListeningChange?.(false);
    }, [onListeningChange]);

    const toggleMic = () => {
        if (listening) {
            stopListening();
        } else {
            startListening();
        }
    };

    return (
        <button
            className={`mic-btn ${listening ? "listening" : ""}`}
            onClick={toggleMic}
            title={
                permissionDenied
                    ? "Microphone access denied"
                    : listening
                        ? "Stop listening"
                        : "Start voice input"
            }
            type="button"
        >
            {listening ? (
                // Stop icon (square)
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
            ) : (
                // Mic icon
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    <line x1="12" y1="19" x2="12" y2="23" />
                    <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
            )}
        </button>
    );
}
