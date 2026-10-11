import React, { useState, useRef, useEffect } from "react";
import { Mic, MicOff, Volume2, VolumeX, Loader2 } from "lucide-react";
import { api } from "../api";
import { AudioRecorder } from "../utils/audioRecorder";

interface VoiceInputButtonProps {
  onTranscribed: (text: string) => void;
  disabled?: boolean;
}

export const VoiceInputButton: React.FC<VoiceInputButtonProps> = ({
  onTranscribed,
  disabled = false,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<AudioRecorder | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (recorderRef.current && recorderRef.current.isRecording) {
        recorderRef.current.cancel();
      }
    };
  }, []);

  const handleStartRecording = async () => {
    if (disabled || isTranscribing) return;
    setError(null);
    try {
      if (!recorderRef.current) {
        recorderRef.current = new AudioRecorder();
      }
      await recorderRef.current.start();
      setIsRecording(true);
      setDuration(0);

      const startTime = Date.now();
      timerRef.current = window.setInterval(() => {
        setDuration(Math.floor((Date.now() - startTime) / 1000));
      }, 500);
    } catch (err: any) {
      console.error("Microphone recording failed to start:", err);
      setError(err?.message || "Failed to access microphone");
      setIsRecording(false);
    }
  };

  const handleStopRecording = async () => {
    if (!recorderRef.current || !isRecording) return;

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsRecording(false);

    try {
      setIsTranscribing(true);
      const audioBlob = await recorderRef.current.stop();
      if (audioBlob.size < 500) {
        setError("Recording too short");
        setIsTranscribing(false);
        return;
      }

      const res = await api.transcribeAudio(audioBlob);
      if (res.text && res.text.trim()) {
        onTranscribed(res.text.trim());
      }
    } catch (err: any) {
      console.error("Audio transcription error:", err);
      setError(err?.message || "Transcription failed");
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleToggle = () => {
    if (isRecording) {
      handleStopRecording();
    } else {
      handleStartRecording();
    }
  };

  const formatDuration = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins}:${s < 10 ? "0" : ""}${s}`;
  };

  return (
    <div className="voice-input-container">
      {error && (
        <div className="voice-tooltip error" title={error}>
          {error.slice(0, 30)}...
        </div>
      )}
      <button
        type="button"
        className={`voice-record-btn ${isRecording ? "recording" : ""} ${
          isTranscribing ? "transcribing" : ""
        }`}
        onClick={handleToggle}
        disabled={disabled || isTranscribing}
        title={
          isRecording
            ? "Click to stop and transcribe"
            : isTranscribing
            ? "Transcribing with local faster-whisper..."
            : "Voice input (push-to-talk)"
        }
      >
        {isTranscribing ? (
          <Loader2 size={18} className="spin" />
        ) : isRecording ? (
          <div className="recording-indicator">
            <MicOff size={18} />
            <span className="rec-time">{formatDuration(duration)}</span>
          </div>
        ) : (
          <Mic size={18} />
        )}
      </button>
    </div>
  );
};

interface SpeakerButtonProps {
  text: string;
}

export const SpeakerButton: React.FC<SpeakerButtonProps> = ({ text }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const handlePlayToggle = async () => {
    if (isPlaying) {
      if (audioRef.current) {
        audioRef.current.pause();
        setIsPlaying(false);
      }
      return;
    }

    if (!text.trim()) return;

    try {
      setIsLoading(true);
      const audioBlob = await api.synthesizeSpeech(text);
      const audioUrl = URL.createObjectURL(audioBlob);

      if (audioRef.current) {
        audioRef.current.pause();
      }

      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
      };

      audio.onerror = () => {
        setIsPlaying(false);
        setIsLoading(false);
        URL.revokeObjectURL(audioUrl);
      };

      await audio.play();
      setIsPlaying(true);
    } catch (err) {
      console.warn("TTS synthesis or playback failed:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button
      type="button"
      className={`speaker-btn ${isPlaying ? "playing" : ""}`}
      onClick={handlePlayToggle}
      title={isPlaying ? "Stop spoken reply" : "Read aloud (Piper TTS)"}
      disabled={isLoading}
    >
      {isLoading ? (
        <Loader2 size={14} className="spin" />
      ) : isPlaying ? (
        <VolumeX size={14} />
      ) : (
        <Volume2 size={14} />
      )}
    </button>
  );
};

interface VoiceSettingsToggleProps {
  ttsEnabled: boolean;
  onToggle: (enabled: boolean) => void;
}

export const VoiceSettingsToggle: React.FC<VoiceSettingsToggleProps> = ({
  ttsEnabled,
  onToggle,
}) => {
  return (
    <button
      type="button"
      className={`btn-tts-toggle ${ttsEnabled ? "active" : ""}`}
      onClick={() => onToggle(!ttsEnabled)}
      title={`Spoken Replies: ${ttsEnabled ? "ON" : "OFF"}`}
    >
      {ttsEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
      <span className="tts-label">TTS {ttsEnabled ? "On" : "Off"}</span>
    </button>
  );
};
