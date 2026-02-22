"use client";

import { useState, useEffect } from "react";

interface WelcomeSplashProps {
    onContinue: () => void;
}

export default function WelcomeSplash({ onContinue }: WelcomeSplashProps) {
    const [show, setShow] = useState(false);
    const [fadeOut, setFadeOut] = useState(false);

    // Fade in on mount
    useEffect(() => {
        const timer = setTimeout(() => setShow(true), 100);
        return () => clearTimeout(timer);
    }, []);

    const handleContinue = () => {
        setFadeOut(true);
        setTimeout(() => onContinue(), 800);
    };

    // Auto-continue after 6 seconds
    useEffect(() => {
        const timer = setTimeout(handleContinue, 6000);
        return () => clearTimeout(timer);
    }, []);

    return (
        <div
            className={`welcome-splash ${show ? "visible" : ""} ${fadeOut ? "fade-out" : ""}`}
            onClick={handleContinue}
        >
            <div className="welcome-content">
                <img
                    src="/Telos logo-Photoroom.png"
                    alt="Telos"
                    className="welcome-logo"
                />
                <h1 className="welcome-title">Welcome to True Agency</h1>
                <p className="welcome-subtitle">
                    Where your intent becomes action — effortlessly.
                </p>
                <button className="welcome-btn" onClick={handleContinue}>
                    Get Started
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12h14" />
                        <path d="m12 5 7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
    );
}
