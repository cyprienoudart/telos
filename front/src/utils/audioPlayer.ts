/**
 * AudioPlayerQueue — Web Audio API based player for streaming TTS audio chunks.
 *
 * Receives base64-encoded PCM audio (24kHz, 16-bit, mono) and plays them
 * seamlessly in sequence. Supports instant queue clearing for interruption.
 */

export class AudioPlayerQueue {
    private audioContext: AudioContext | null = null;
    private queue: AudioBuffer[] = [];
    private isPlaying = false;
    private currentSource: AudioBufferSourceNode | null = null;
    private analyser: AnalyserNode | null = null;
    private onAmplitudeChange?: (level: number) => void;
    private onPlaybackEnd?: () => void;
    private animFrame = 0;

    constructor(opts?: {
        onAmplitudeChange?: (level: number) => void;
        onPlaybackEnd?: () => void;
    }) {
        this.onAmplitudeChange = opts?.onAmplitudeChange;
        this.onPlaybackEnd = opts?.onPlaybackEnd;
    }

    private getContext(): AudioContext {
        if (!this.audioContext) {
            this.audioContext = new AudioContext({ sampleRate: 24000 });
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.analyser.connect(this.audioContext.destination);
        }
        return this.audioContext;
    }

    /**
     * Enqueue a base64-encoded PCM chunk for playback.
     * PCM format: 16-bit signed little-endian, mono, 24kHz
     */
    async enqueue(base64Audio: string) {
        const ctx = this.getContext();
        if (ctx.state === "suspended") {
            await ctx.resume();
        }

        // Decode base64 to raw bytes
        const binaryString = atob(base64Audio);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        // Convert PCM 16-bit to Float32 for Web Audio API
        const int16 = new Int16Array(bytes.buffer);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768;
        }

        // Create AudioBuffer
        const buffer = ctx.createBuffer(1, float32.length, 24000);
        buffer.getChannelData(0).set(float32);

        this.queue.push(buffer);

        if (!this.isPlaying) {
            this.playNext();
        }
    }

    private playNext() {
        if (this.queue.length === 0) {
            this.isPlaying = false;
            this.onAmplitudeChange?.(0);
            this.onPlaybackEnd?.();
            cancelAnimationFrame(this.animFrame);
            return;
        }

        this.isPlaying = true;
        const ctx = this.getContext();
        const buffer = this.queue.shift()!;

        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(this.analyser!);
        this.currentSource = source;

        source.onended = () => {
            this.currentSource = null;
            this.playNext();
        };

        source.start();
        this.startAmplitudeMonitor();
    }

    private startAmplitudeMonitor() {
        if (!this.analyser || !this.onAmplitudeChange) return;

        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);

        const measure = () => {
            if (!this.isPlaying) return;
            this.analyser!.getByteFrequencyData(dataArray);

            // Calculate RMS amplitude normalized to 0–1
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i] * dataArray[i];
            }
            const rms = Math.sqrt(sum / dataArray.length) / 255;
            this.onAmplitudeChange!(Math.min(1, rms * 2.5)); // Boost a bit

            this.animFrame = requestAnimationFrame(measure);
        };

        this.animFrame = requestAnimationFrame(measure);
    }

    /** Immediately stop playback and clear all queued chunks */
    clearQueue() {
        this.queue = [];
        if (this.currentSource) {
            try {
                this.currentSource.stop();
            } catch {
                // Already stopped
            }
            this.currentSource = null;
        }
        this.isPlaying = false;
        cancelAnimationFrame(this.animFrame);
        this.onAmplitudeChange?.(0);
    }

    /** Get current playback state */
    getIsPlaying() {
        return this.isPlaying;
    }

    /** Cleanup */
    destroy() {
        this.clearQueue();
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
    }
}
