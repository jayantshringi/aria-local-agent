import React, { useEffect, useState, useCallback } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatArea } from "./components/ChatArea";
import { MessageInput } from "./components/MessageInput";
import { LoginModal } from "./components/LoginModal";
import { MemoryModal } from "./components/MemoryModal";
import { useChat } from "./hooks/useChat";
import { api, getStoredDevice, getStoredToken, clearStoredAuth, storeAuth } from "./api";
import { Device, Session } from "./types";

export const App: React.FC = () => {
  const [token, setToken] = useState<string | null>(getStoredToken());
  const [device, setDevice] = useState<Device | null>(getStoredDevice());
  const [showLoginModal, setShowLoginModal] = useState<boolean>(!token);
  const [isMemoryModalOpen, setIsMemoryModalOpen] = useState<boolean>(false);
  const [memoryInitialTab, setMemoryInitialTab] = useState<"about" | "search">("about");

  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  // Load sessions from API
  const refreshSessions = useCallback(async () => {
    if (!token) return;
    try {
      const list = await api.listSessions();
      setSessions(list);
      // Auto-select first session if none selected
      if (!activeSessionId && list.length > 0) {
        setActiveSessionId(list[0].id);
      }
    } catch (err) {
      console.error("Failed to load sessions", err);
    }
  }, [token, activeSessionId]);

  useEffect(() => {
    if (token) {
      refreshSessions();
    }
  }, [token, refreshSessions]);

  const handleSessionCreated = useCallback((newSession: Session) => {
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
  }, []);

  const {
    messages,
    streamingContent,
    isStreaming,
    isConnected,
    errorMessage,
    sendMessage,
    setErrorMessage,
  } = useChat({
    activeSessionId,
    onSessionCreated: handleSessionCreated,
  });

  const handleLoginSuccess = (newToken: string, newDevice: Device) => {
    storeAuth(newToken, newDevice);
    setToken(newToken);
    setDevice(newDevice);
    setShowLoginModal(false);
  };

  const handleLogout = () => {
    clearStoredAuth();
    setToken(null);
    setDevice(null);
    setSessions([]);
    setActiveSessionId(null);
    setShowLoginModal(true);
  };

  const handleNewChat = () => {
    setActiveSessionId(null);
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to delete session");
    }
  };

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const currentTitle = activeSession ? activeSession.title : "New Chat";

  return (
    <div className="app-container">
      <LoginModal isOpen={showLoginModal} onSuccess={handleLoginSuccess} />

      <MemoryModal
        isOpen={isMemoryModalOpen}
        onClose={() => setIsMemoryModalOpen(false)}
        initialTab={memoryInitialTab}
        onSelectSession={setActiveSessionId}
      />

      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={setActiveSessionId}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        currentDevice={device}
        onLogout={handleLogout}
        onOpenMemory={(tab) => {
          setMemoryInitialTab(tab);
          setIsMemoryModalOpen(true);
        }}
      />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
        <ChatArea
          sessionTitle={currentTitle}
          messages={messages}
          streamingContent={streamingContent}
          isStreaming={isStreaming}
          isConnected={isConnected}
          errorMessage={errorMessage}
          onClearError={() => setErrorMessage(null)}
        />

        <MessageInput onSendMessage={sendMessage} disabled={isStreaming} />
      </div>
    </div>
  );
};

export default App;
