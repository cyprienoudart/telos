import { NextRequest } from "next/server";

const ELEVENLABS_TTS_WS_BASE = "wss://api.elevenlabs.io/v1/text-to-speech";
const VOICE_ID = "21m00Tcm4TlvDq8ikWAM"; // Rachel — default ElevenLabs voice
const MODEL_ID = "eleven_flash_v2_5";

export async function POST(request: NextRequest) {
    const apiKey = process.env.ELEVENLABS_API_KEY;
    if (!apiKey) {
        return new Response(JSON.stringify({ error: "API key not configured" }), {
            status: 500,
        });
    }

    let body: { text: string };
    try {
        body = await request.json();
    } catch {
        return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
            status: 400,
        });
    }

    const { text } = body;
    if (!text) {
        return new Response(JSON.stringify({ error: "Text is required" }), {
            status: 400,
        });
    }

    // Stream TTS via ElevenLabs WebSocket and return audio chunks as SSE
    const encoder = new TextEncoder();

    const stream = new ReadableStream({
        async start(controller) {
            try {
                const wsUrl = `${ELEVENLABS_TTS_WS_BASE}/${VOICE_ID}/stream-input?model_id=${MODEL_ID}`;

                // Use native WebSocket (available in Node 22+)
                const ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    // Send initial config
                    ws.send(
                        JSON.stringify({
                            text: " ",
                            voice_settings: {
                                stability: 0.5,
                                similarity_boost: 0.75,
                            },
                            xi_api_key: apiKey,
                            output_format: "pcm_24000",
                        })
                    );

                    // Send the actual text
                    ws.send(JSON.stringify({ text: text + " " }));

                    // Signal end of text
                    ws.send(JSON.stringify({ text: "" }));
                };

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(
                            typeof event.data === "string" ? event.data : ""
                        );

                        if (data.audio) {
                            // Send audio chunk as SSE event
                            const sseData = `data: ${JSON.stringify({ audio: data.audio })}\n\n`;
                            controller.enqueue(encoder.encode(sseData));
                        }

                        if (data.isFinal) {
                            controller.enqueue(encoder.encode("data: [DONE]\n\n"));
                            controller.close();
                            ws.close();
                        }
                    } catch (e) {
                        // Non-JSON message, ignore
                    }
                };

                ws.onerror = (err) => {
                    console.error("TTS WebSocket error:", err);
                    controller.enqueue(
                        encoder.encode(
                            `data: ${JSON.stringify({ error: "TTS stream error" })}\n\n`
                        )
                    );
                    controller.close();
                };

                ws.onclose = () => {
                    try {
                        controller.close();
                    } catch {
                        // Already closed
                    }
                };

                // Timeout safety — close after 30s
                setTimeout(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.close();
                    }
                    try {
                        controller.close();
                    } catch {
                        // Already closed
                    }
                }, 30000);
            } catch (error) {
                console.error("TTS stream setup error:", error);
                controller.enqueue(
                    encoder.encode(
                        `data: ${JSON.stringify({ error: "Stream setup failed" })}\n\n`
                    )
                );
                controller.close();
            }
        },
    });

    return new Response(stream, {
        headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            Connection: "keep-alive",
        },
    });
}
