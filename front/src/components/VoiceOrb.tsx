"use client";

import { useEffect, useRef, useCallback } from "react";

type OrbMode = "idle" | "listening" | "loading" | "speaking";

interface VoiceOrbProps {
    mode: OrbMode;
    audioLevel?: number; // 0–1
}

// ---- Geometry helpers ----

function lerp(a: number, b: number, t: number) {
    return a + (b - a) * t;
}

interface Point {
    x: number;
    y: number;
    baseX: number;
    baseY: number;
    angle: number;
    speed: number;
    radius: number;
}

function createPoints(cx: number, cy: number, count: number, radius: number): Point[] {
    const pts: Point[] = [];
    for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2;
        const x = cx + Math.cos(angle) * radius;
        const y = cy + Math.sin(angle) * radius;
        pts.push({
            x,
            y,
            baseX: x,
            baseY: y,
            angle: Math.random() * Math.PI * 2,
            speed: 0.02 + Math.random() * 0.03,
            radius: radius,
        });
    }
    return pts;
}

// ---- Particle system for loading state ----

interface Particle {
    angle: number;
    dist: number;
    speed: number;
    size: number;
    opacity: number;
}

function createParticles(count: number, maxDist: number): Particle[] {
    return Array.from({ length: count }, () => ({
        angle: Math.random() * Math.PI * 2,
        dist: 30 + Math.random() * maxDist,
        speed: 0.005 + Math.random() * 0.015,
        size: 1 + Math.random() * 2.5,
        opacity: 0.3 + Math.random() * 0.5,
    }));
}

export default function VoiceOrb({ mode, audioLevel = 0 }: VoiceOrbProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const animRef = useRef<number>(0);
    const pointsRef = useRef<Point[]>([]);
    const particlesRef = useRef<Particle[]>([]);
    const timeRef = useRef(0);
    const smoothLevelRef = useRef(0);
    const modeRef = useRef<OrbMode>(mode);
    const audioLevelRef = useRef(audioLevel);

    modeRef.current = mode;
    audioLevelRef.current = audioLevel;

    const draw = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const w = canvas.clientWidth;
        const h = canvas.clientHeight;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);

        const cx = w / 2;
        const cy = h / 2;
        const baseRadius = Math.min(w, h) * 0.28;
        const currentMode = modeRef.current;
        const level = audioLevelRef.current;

        // Smooth audio level
        smoothLevelRef.current = lerp(smoothLevelRef.current, level, 0.12);
        const sl = smoothLevelRef.current;

        timeRef.current += 1;
        const t = timeRef.current;

        // Init points if needed
        if (pointsRef.current.length === 0) {
            pointsRef.current = createPoints(cx, cy, 64, baseRadius);
        }
        if (particlesRef.current.length === 0) {
            particlesRef.current = createParticles(40, baseRadius * 0.8);
        }

        ctx.clearRect(0, 0, w, h);

        const pts = pointsRef.current;

        // ---- Update points based on mode ----
        for (let i = 0; i < pts.length; i++) {
            const p = pts[i];
            const baseAngle = (i / pts.length) * Math.PI * 2;
            p.angle += p.speed;

            let displacement = 0;

            if (currentMode === "listening") {
                // React to audio: vertices expand with amplitude
                const wave = Math.sin(baseAngle * 3 + t * 0.05) * 0.5 + 0.5;
                displacement = sl * baseRadius * 0.4 * wave + Math.sin(p.angle) * 3;
            } else if (currentMode === "loading") {
                // Smooth morphing — organic blob
                displacement =
                    Math.sin(baseAngle * 2 + t * 0.03) * baseRadius * 0.12 +
                    Math.sin(baseAngle * 5 + t * 0.06) * baseRadius * 0.06 +
                    Math.cos(p.angle) * 4;
            } else if (currentMode === "speaking") {
                // Waveform-like pulsation from TTS output
                const wave = Math.sin(baseAngle * 6 + t * 0.08);
                displacement = sl * baseRadius * 0.35 * Math.abs(wave) + Math.sin(p.angle) * 2;
            } else {
                // Idle: gentle breathing
                displacement = Math.sin(t * 0.02 + baseAngle) * baseRadius * 0.03;
            }

            const r = baseRadius + displacement;
            p.x = lerp(p.x, cx + Math.cos(baseAngle) * r, 0.1);
            p.y = lerp(p.y, cy + Math.sin(baseAngle) * r, 0.1);
        }

        // ---- Draw the main shape ----

        // Glow
        const glowAlpha = currentMode === "idle" ? 0.06 : 0.15 + sl * 0.15;
        const glowColor =
            currentMode === "listening"
                ? `rgba(99, 102, 241, ${glowAlpha})`
                : currentMode === "loading"
                    ? `rgba(168, 85, 247, ${glowAlpha})`
                    : currentMode === "speaking"
                        ? `rgba(59, 130, 246, ${glowAlpha})`
                        : `rgba(150, 150, 150, ${glowAlpha})`;

        const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseRadius * 1.6);
        gradient.addColorStop(0, glowColor);
        gradient.addColorStop(1, "transparent");
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, w, h);

        // Main shape path via smooth Catmull-Rom-ish spline
        ctx.beginPath();
        for (let i = 0; i < pts.length; i++) {
            const p0 = pts[(i - 1 + pts.length) % pts.length];
            const p1 = pts[i];
            const p2 = pts[(i + 1) % pts.length];

            const cpx = (p0.x + p2.x) / 2;
            const cpy = (p0.y + p2.y) / 2;

            if (i === 0) {
                ctx.moveTo((p0.x + p1.x) / 2, (p0.y + p1.y) / 2);
            }
            ctx.quadraticCurveTo(p1.x, p1.y, (p1.x + p2.x) / 2, (p1.y + p2.y) / 2);
        }
        ctx.closePath();

        // Fill
        const fillGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseRadius * 1.2);
        if (currentMode === "listening") {
            fillGrad.addColorStop(0, "rgba(99, 102, 241, 0.12)");
            fillGrad.addColorStop(1, "rgba(99, 102, 241, 0.03)");
        } else if (currentMode === "loading") {
            fillGrad.addColorStop(0, "rgba(168, 85, 247, 0.10)");
            fillGrad.addColorStop(1, "rgba(168, 85, 247, 0.02)");
        } else if (currentMode === "speaking") {
            fillGrad.addColorStop(0, "rgba(59, 130, 246, 0.12)");
            fillGrad.addColorStop(1, "rgba(59, 130, 246, 0.03)");
        } else {
            fillGrad.addColorStop(0, "rgba(180, 180, 180, 0.06)");
            fillGrad.addColorStop(1, "rgba(180, 180, 180, 0.01)");
        }
        ctx.fillStyle = fillGrad;
        ctx.fill();

        // Stroke
        const strokeColor =
            currentMode === "listening"
                ? `rgba(99, 102, 241, ${0.3 + sl * 0.4})`
                : currentMode === "loading"
                    ? `rgba(168, 85, 247, ${0.25 + Math.sin(t * 0.04) * 0.15})`
                    : currentMode === "speaking"
                        ? `rgba(59, 130, 246, ${0.3 + sl * 0.4})`
                        : "rgba(200, 200, 200, 0.15)";

        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = currentMode === "idle" ? 1 : 1.5;
        ctx.stroke();

        // ---- Inner geometric mesh (for listening/speaking) ----
        if (currentMode === "listening" || currentMode === "speaking") {
            ctx.save();
            ctx.globalAlpha = 0.08 + sl * 0.12;
            ctx.strokeStyle =
                currentMode === "listening"
                    ? "rgba(99, 102, 241, 0.5)"
                    : "rgba(59, 130, 246, 0.5)";
            ctx.lineWidth = 0.5;

            const step = Math.max(4, Math.floor(pts.length / 8));
            for (let i = 0; i < pts.length; i += step) {
                for (let j = i + step; j < pts.length; j += step) {
                    ctx.beginPath();
                    ctx.moveTo(pts[i].x, pts[i].y);
                    ctx.lineTo(pts[j].x, pts[j].y);
                    ctx.stroke();
                }
            }
            ctx.restore();
        }

        // ---- Particles (for loading) ----
        if (currentMode === "loading") {
            const particles = particlesRef.current;
            for (const p of particles) {
                p.angle += p.speed;
                const px = cx + Math.cos(p.angle) * p.dist;
                const py = cy + Math.sin(p.angle) * p.dist;

                ctx.beginPath();
                ctx.arc(px, py, p.size, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(168, 85, 247, ${p.opacity * (0.5 + Math.sin(t * 0.05 + p.angle) * 0.5)})`;
                ctx.fill();
            }
        }

        // ---- Center dot ----
        const dotRadius = currentMode === "idle" ? 3 : 4 + sl * 3;
        const dotColor =
            currentMode === "listening"
                ? "rgba(99, 102, 241, 0.6)"
                : currentMode === "loading"
                    ? "rgba(168, 85, 247, 0.5)"
                    : currentMode === "speaking"
                        ? "rgba(59, 130, 246, 0.6)"
                        : "rgba(180, 180, 180, 0.2)";

        ctx.beginPath();
        ctx.arc(cx, cy, dotRadius, 0, Math.PI * 2);
        ctx.fillStyle = dotColor;
        ctx.fill();

        animRef.current = requestAnimationFrame(draw);
    }, []);

    useEffect(() => {
        animRef.current = requestAnimationFrame(draw);
        return () => cancelAnimationFrame(animRef.current);
    }, [draw]);

    // Reset points when mode changes to get fresh geometry
    useEffect(() => {
        pointsRef.current = [];
    }, [mode]);

    return (
        <div className="voice-orb-container">
            <canvas
                ref={canvasRef}
                className="voice-orb-canvas"
                style={{ width: "100%", height: "100%" }}
            />
            {mode !== "idle" && (
                <div className="voice-orb-label">
                    {mode === "listening" && "Listening..."}
                    {mode === "loading" && "Thinking..."}
                    {mode === "speaking" && "Speaking..."}
                </div>
            )}
        </div>
    );
}
