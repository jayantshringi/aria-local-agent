import React from "react";
import { MessageSquare, Plus, Trash2, Laptop, ShieldCheck, LogOut } from "lucide-react";
import { Device, Session } from "../types";

interface SidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  currentDevice: Device | null;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  currentDevice,
  onLogout,
}) => {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand">
          <div className="brand-logo">
            <ShieldCheck size={20} color="#fff" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span className="brand-title">Aria</span>
              <span className="brand-badge">Local</span>
            </div>
          </div>
        </div>
      </div>

      <div className="sidebar-actions">
        <button className="btn btn-primary new-chat-btn" onClick={onNewChat}>
          <Plus size={18} />
          <span>New Chat</span>
        </button>
      </div>

      <div className="session-list">
        {sessions.length === 0 ? (
          <div style={{ padding: "20px 10px", textAlign: "center", color: "var(--text-muted)", fontSize: "0.85rem" }}>
            No sessions yet. Start a new conversation!
          </div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.id}
              className={`session-item ${session.id === activeSessionId ? "active" : ""}`}
              onClick={() => onSelectSession(session.id)}
            >
              <MessageSquare size={16} style={{ flexShrink: 0, marginRight: 8, opacity: 0.7 }} />
              <span className="session-item-title">{session.title || "Untitled Session"}</span>
              <button
                className="btn-icon session-item-delete"
                title="Delete session"
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm("Delete this chat session permanently?")) {
                    onDeleteSession(session.id);
                  }
                }}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden" }}>
          <Laptop size={14} />
          <span style={{ textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
            {currentDevice ? currentDevice.name : "Local Client"}
          </span>
        </div>
        <button className="btn-icon" title="Log out / Revoke device" onClick={onLogout}>
          <LogOut size={14} />
        </button>
      </div>
    </aside>
  );
};
