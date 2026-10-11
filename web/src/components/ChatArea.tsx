import React, { useEffect, useRef } from "react";
import { AlertCircle, Bot, Sparkles, User } from "lucide-react";
import { KillSwitchStatus, Message, PendingAction } from "../types";
import { ActionApprovalBanner } from "./ActionApprovalBanner";
import { KillSwitchButton } from "./KillSwitchButton";
import { SpeakerButton, VoiceSettingsToggle } from "./VoiceControls";

interface ChatAreaProps {
  sessionTitle: string;
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  isConnected: boolean;
  errorMessage: string | null;
  onClearError: () => void;
  killSwitchStatus: KillSwitchStatus;
  onKillSwitchStatusChange: (status: KillSwitchStatus) => void;
  onKilled?: () => void;
  pendingActions: PendingAction[];
  onActionResolved: (actionId: string, status: string) => void;
  onOpenAuditLog: () => void;
  ttsEnabled?: boolean;
  onToggleTts?: (enabled: boolean) => void;
}

// Simple and safe markdown formatter for code blocks, inline code, bold, lists, and paragraphs
function renderMarkdownContent(text: string) {
  const parts = text.split(/(```[\s\S]*?```)/g);

  return parts.map((part, index) => {
    if (part.startsWith("```") && part.endsWith("```")) {
      const firstNewline = part.indexOf("\n");
      const code = firstNewline !== -1 ? part.slice(firstNewline + 1, -3) : part.slice(3, -3);
      const lang = firstNewline !== -1 ? part.slice(3, firstNewline).trim() : "";

      return (
        <pre key={index}>
          {lang && (
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase" }}>
              {lang}
            </div>
          )}
          <code>{code}</code>
        </pre>
      );
    }

    // Process inline text line by line
    const lines = part.split("\n");
    return (
      <React.Fragment key={index}>
        {lines.map((line, lIdx) => {
          if (!line.trim()) {
            return <div key={lIdx} style={{ height: "8px" }} />;
          }

          // Handle bullet lists
          if (line.startsWith("- ") || line.startsWith("* ")) {
            return (
              <li key={lIdx} style={{ marginLeft: 20 }}>
                {formatInlineText(line.slice(2))}
              </li>
            );
          }

          return (
            <p key={lIdx} style={{ margin: "4px 0" }}>
              {formatInlineText(line)}
            </p>
          );
        })}
      </React.Fragment>
    );
  });
}

function formatInlineText(text: string) {
  // Simple inline processor for `code` and **bold**
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return tokens.map((token, i) => {
    if (token.startsWith("`") && token.endsWith("`")) {
      return <code key={i}>{token.slice(1, -1)}</code>;
    }
    if (token.startsWith("**") && token.endsWith("**")) {
      return <strong key={i}>{token.slice(2, -2)}</strong>;
    }
    return token;
  });
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  sessionTitle,
  messages,
  streamingContent,
  isStreaming,
  isConnected,
  errorMessage,
  onClearError,
  killSwitchStatus,
  onKillSwitchStatusChange,
  onKilled,
  pendingActions,
  onActionResolved,
  onOpenAuditLog,
  ttsEnabled,
  onToggleTts,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on message updates or streaming tokens
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingContent]);

  return (
    <div className="chat-main">
      <header className="chat-header">
        <div className="chat-header-title">
          <span>{sessionTitle || "New Conversation"}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {onToggleTts && (
            <VoiceSettingsToggle
              ttsEnabled={ttsEnabled ?? false}
              onToggle={onToggleTts}
            />
          )}
          <KillSwitchButton
            status={killSwitchStatus}
            onStatusChange={onKillSwitchStatusChange}
            onKilled={onKilled}
          />
          <div className="status-pill">
            <span className={`status-dot ${isConnected ? "online" : "offline"}`} />
            <span>{isConnected ? "Connected" : "Disconnected"}</span>
          </div>
        </div>
      </header>

      {/* Floating or Top Action Approval Banner */}
      <ActionApprovalBanner
        pendingActions={pendingActions}
        onActionResolved={onActionResolved}
        onOpenAuditLog={onOpenAuditLog}
      />

      {errorMessage && (
        <div style={{ padding: "12px 24px", maxWidth: 860, margin: "10px auto 0", width: "100%" }}>
          <div className="error-banner" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <AlertCircle size={18} />
              <span>{errorMessage}</span>
            </div>
            <button className="btn-icon" onClick={onClearError} style={{ color: "#fca5a5" }}>
              ✕
            </button>
          </div>
        </div>
      )}

      <div className="messages-container" ref={scrollRef}>
        {messages.length === 0 && !isStreaming ? (
          <div className="welcome-hero">
            <div className="welcome-icon">
              <Sparkles size={32} color="#fff" />
            </div>
            <h1 className="welcome-title">Welcome to Aria</h1>
            <p className="welcome-subtitle">
              Your 100% private, local-first personal AI assistant. No cloud dependencies, no tracking, complete hardware ownership.
            </p>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <div key={msg.id} className={`message-row ${msg.role}`}>
                <div className={`message-avatar ${msg.role}`}>
                  {msg.role === "assistant" ? <Bot size={20} /> : <User size={20} />}
                </div>
                <div className={`message-bubble ${msg.role}`}>
                  {msg.role === "assistant" ? renderMarkdownContent(msg.content) : msg.content}
                  <div className="message-meta-bar">
                    <span className="message-time">
                      {new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                    {msg.role === "assistant" && <SpeakerButton text={msg.content} />}
                  </div>
                </div>
              </div>
            ))}

            {isStreaming && (
              <div className="message-row assistant">
                <div className="message-avatar assistant">
                  <Bot size={20} />
                </div>
                <div className="message-bubble assistant">
                  {renderMarkdownContent(streamingContent)}
                  <span className="typing-cursor" />
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
