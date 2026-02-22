import { NextResponse } from "next/server";

export async function GET() {
    const apiKey = process.env.ELEVENLABS_API_KEY;

    if (!apiKey) {
        return NextResponse.json(
            { error: "ELEVENLABS_API_KEY not configured" },
            { status: 500 }
        );
    }

    try {
        // Generate a single-use token for realtime_scribe
        const response = await fetch(
            "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe",
            {
                method: "POST",
                headers: {
                    "xi-api-key": apiKey,
                    "Content-Type": "application/json",
                },
            }
        );

        if (!response.ok) {
            const errorText = await response.text();
            console.error("ElevenLabs token error:", response.status, errorText);
            return NextResponse.json(
                { error: "Failed to generate scribe token", details: errorText },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json({ token: data.token });
    } catch (error) {
        console.error("Scribe token error:", error);
        return NextResponse.json(
            { error: "Internal server error" },
            { status: 500 }
        );
    }
}
