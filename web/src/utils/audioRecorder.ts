/**
 * Browser Web Audio API 16kHz 16-bit mono linear PCM WAV recorder.
 * Zero external libraries, zero system ffmpeg dependency.
 */

export class AudioRecorder {
  private stream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private processorNode: ScriptProcessorNode | null = null;
  private recordedSamples: Float32Array[] = [];
  private totalSamples = 0;
  private recording = false;

  public get isRecording(): boolean {
    return this.recording;
  }

  /**
   * Start recording audio from the user's microphone.
   */
  public async start(): Promise<void> {
    if (this.recording) return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Microphone access is not supported by this browser.");
    }

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });

    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    this.audioContext = new AudioContextClass();

    this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);
    // 4096 samples buffer, 1 input channel, 1 output channel
    this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1);

    this.recordedSamples = [];
    this.totalSamples = 0;

    this.processorNode.onaudioprocess = (e: AudioProcessingEvent) => {
      if (!this.recording) return;
      const channelData = e.inputBuffer.getChannelData(0);
      const copy = new Float32Array(channelData);
      this.recordedSamples.push(copy);
      this.totalSamples += copy.length;
    };

    this.sourceNode.connect(this.processorNode);
    this.processorNode.connect(this.audioContext.destination);

    this.recording = true;
  }

  /**
   * Stop recording, cleanup microphone streams, and return encoded WAV Blob.
   */
  public async stop(): Promise<Blob> {
    if (!this.recording) {
      throw new Error("Recorder is not active.");
    }

    this.recording = false;

    // Disconnect audio graph
    if (this.sourceNode && this.processorNode) {
      this.sourceNode.disconnect();
      this.processorNode.disconnect();
    }

    // Stop all microphone tracks to release hardware
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }

    const currentSampleRate = this.audioContext ? this.audioContext.sampleRate : 48000;
    if (this.audioContext && this.audioContext.state !== "closed") {
      await this.audioContext.close();
      this.audioContext = null;
    }

    // Merge recorded chunks
    const merged = new Float32Array(this.totalSamples);
    let offset = 0;
    for (const chunk of this.recordedSamples) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    this.recordedSamples = [];
    this.totalSamples = 0;

    // Resample to 16,000 Hz if source rate differs
    const targetSampleRate = 16000;
    const resampled = this.resampleTo16k(merged, currentSampleRate, targetSampleRate);

    // Convert float32 to int16 PCM
    const pcm16 = new Int16Array(resampled.length);
    for (let i = 0; i < resampled.length; i++) {
      const s = Math.max(-1, Math.min(1, resampled[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    // Build standard 44-byte WAV header + PCM payload
    const wavBytes = this.encodeWAV(pcm16, targetSampleRate);
    return new Blob([wavBytes], { type: "audio/wav" });
  }

  /**
   * Cancel and discard recording immediately.
   */
  public cancel(): void {
    this.recording = false;
    if (this.sourceNode && this.processorNode) {
      this.sourceNode.disconnect();
      this.processorNode.disconnect();
    }
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close();
      this.audioContext = null;
    }
    this.recordedSamples = [];
    this.totalSamples = 0;
  }

  private resampleTo16k(
    samples: Float32Array,
    fromRate: number,
    toRate: number
  ): Float32Array {
    if (fromRate === toRate || samples.length === 0) {
      return samples;
    }

    const ratio = fromRate / toRate;
    const newLength = Math.round(samples.length / ratio);
    const result = new Float32Array(newLength);

    for (let i = 0; i < newLength; i++) {
      const originIndex = i * ratio;
      const lowerIndex = Math.floor(originIndex);
      const upperIndex = Math.min(lowerIndex + 1, samples.length - 1);
      const weight = originIndex - lowerIndex;
      result[i] = samples[lowerIndex] * (1 - weight) + samples[upperIndex] * weight;
    }

    return result;
  }

  private encodeWAV(samples: Int16Array, sampleRate: number): ArrayBuffer {
    const numChannels = 1;
    const bytesPerSample = 2;
    const blockAlign = numChannels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataSize = samples.length * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);

    const writeString = (view: DataView, offset: number, str: string) => {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
      }
    };

    // RIFF chunk descriptor
    writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + dataSize, true);
    writeString(view, 8, "WAVE");

    // fmt sub-chunk
    writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
    view.setUint16(20, 1, true); // AudioFormat (1 = Linear PCM)
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bytesPerSample * 8, true); // BitsPerSample (16)

    // data sub-chunk
    writeString(view, 36, "data");
    view.setUint32(40, dataSize, true);

    // Copy PCM samples
    const outputBytes = new Uint8Array(buffer, 44);
    const sampleBytes = new Uint8Array(samples.buffer, samples.byteOffset, samples.byteLength);
    outputBytes.set(sampleBytes);

    return buffer;
  }
}
