"use client";

import { useEffect, useRef, useState } from "react";

interface VideoIntroProps {
    onComplete: () => void;
}

export default function VideoIntro({ onComplete }: VideoIntroProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [fadingOut, setFadingOut] = useState(false);

    const handleTransition = () => {
        if (fadingOut) return;
        setFadingOut(true);
        setTimeout(() => {
            onComplete();
        }, 600);
    };

    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === " " || e.key === "Enter") {
                e.preventDefault();
                handleTransition();
            }
        };
        window.addEventListener("keydown", handleKey);
        return () => window.removeEventListener("keydown", handleKey);
    });

    return (
        <div
            className={`video-container ${fadingOut ? "fade-out" : ""}`}
            onClick={handleTransition}
        >
            <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                onEnded={handleTransition}
            >
                <source src="/Rendu Telos entry.mp4" type="video/mp4" />
            </video>
        </div>
    );
}
