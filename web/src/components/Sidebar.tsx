import React from "react";
import {
  Bell,
  BellRing,
  Download,
  Laptop,
  LogOut,
  MessageSquare,
  Plus,
  Search,
  ShieldCheck,
  Smartphone,
  Trash2,
  UserCheck,
} from "lucide-react";
import { Device, Session } from "../types";

interface SidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  currentDevice: Device | null;
  onLogout: () => void;
  onOpenMemory: (tab: "about" | "search") => void;
  onOpenDevices: () => void;
  onOpenAuditLog: () => void;
  pendingActionsCount?: number;
  canInstallPwa?: boolean;
  onInstallPwa?: () => void;
  notificationsEnabled?: boolean;
  onRequestNotifications?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  currentDevice,
  onLogout,
  onOpenMemory,
  onOpenDevices,
  onOpenAuditLog,
  pendingActionsCount = 0,
  canInstallPwa,
  onInstallPwa,
  notificationsEnabled,
  onRequestNotifications,
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
        <div className="sidebar-memory-btns">
          <button
            className="btn btn-secondary memory-action-btn"
            title="Search past chats & memory"
            onClick={() => onOpenMemory("search")}
          >
            <Search size={15} />
            <span>Search</span>
          </button>
          <button
            className="btn btn-secondary memory-action-btn"
            title="Profile Memory & Facts (About Me)"
            onClick={() => onOpenMemory("about")}
          >
            <UserCheck size={15} />
            <span>About Me</span>
          </button>
        </div>

        <div className="sidebar-device-btns">
          <button
            className="btn btn-secondary device-action-btn"
            title="Manage paired devices and generate QR shortcode"
            onClick={onOpenDevices}
          >
            <Smartphone size={15} />
            <span>Devices & Sync</span>
          </button>
          <button
            className="btn btn-secondary audit-action-btn"
            title="Inspect Agent Security & Audit Log"
            onClick={onOpenAuditLog}
          >
            <ShieldCheck size={15} />
            <span>Audit Log</span>
            {pendingActionsCount > 0 && (
              <span className="sidebar-pending-badge" title={`${pendingActionsCount} action(s) pending approval`}>
                {pendingActionsCount}
              </span>
            )}
          </button>
        </div>
        {canInstallPwa && onInstallPwa && (
          <div style={{ marginTop: 6 }}>
            <button
              className="btn btn-accent install-pwa-btn"
              title="Install Aria as a native app on your phone or desktop"
              onClick={onInstallPwa}
            >
              <Download size={15} />
              <span>Install App</span>
            </button>
          </div>
        )}
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
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {onRequestNotifications && (
            <button
              className="btn-icon"
              title={notificationsEnabled ? "Notifications active" : "Enable background notifications"}
              onClick={onRequestNotifications}
            >
              {notificationsEnabled ? <BellRing size={14} color="#06B6D4" /> : <Bell size={14} />}
            </button>
          )}
          <button className="btn-icon" title="Log out / Revoke device" onClick={onLogout}>
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
};
