import React, { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import { VoiceInputButton } from "./VoiceControls";

interface MessageInputProps {
  onSendMessage: (text: string) => void;
  disabled: boolean;
}

export const MessageInput: React.FC<MessageInputProps> = ({ onSendMessage, disabled }) => {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (!input.trim() || disabled) return;
    onSendMessage(input);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleVoiceTranscribed = (text: string) => {
    if (!text.trim()) return;
    setInput((prev) => (prev ? `${prev} ${text}` : text));
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  return (
    <div className="chat-input-wrapper">
      <div className="input-box">
        <textarea
          ref={textareaRef}
          className="chat-textarea"
          placeholder="Ask Aria anything... (Shift+Enter for newline)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
        />
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <VoiceInputButton onTranscribed={handleVoiceTranscribed} disabled={disabled} />
          <button
            className="send-btn"
            onClick={handleSubmit}
            disabled={!input.trim() || disabled}
            title="Send message"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};

