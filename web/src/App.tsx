import React, { useCallback, useEffect, useState } from "react";
import { api, clearStoredAuth, getStoredDevice, getStoredToken, storeAuth } from "./api";
import { ChatArea } from "./components/ChatArea";
import { DeviceModal } from "./components/DeviceModal";
import { LoginModal } from "./components/LoginModal";
import { MemoryModal } from "./components/MemoryModal";
import { MessageInput } from "./components/MessageInput";
import { Sidebar } from "./components/Sidebar";
import { useChat } from "./hooks/useChat";
import { Device, Session } from "./types";

export const App: React.FC = () => {
  const [token, setToken] = useState<string | null>(getStoredToken());
  const [device, setDevice] = useState<Device | null>(getStoredDevice());
  const [showLoginModal, setShowLoginModal] = useState<boolean>(!token);
  const [initialPairCode, setInitialPairCode] = useState<string | null>(null);

  const [isMemoryModalOpen, setIsMemoryModalOpen] = useState<boolean>(false);
  const [memoryInitialTab, setMemoryInitialTab] = useState<"about" | "search">("about");
  const [isDeviceModalOpen, setIsDeviceModalOpen] = useState<boolean>(false);

  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  // PWA Install Prompt State
  const [installPromptEvent, setInstallPromptEvent] = useState<any>(null);

  // Notification Permissions State
  const [notificationsEnabled, setNotificationsEnabled] = useState<boolean>(
    typeof Notification !== "undefined" && Notification.permission === "granted"
  );

  // Parse ?pair=<code> URL query parameter on initial load
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pairCode = params.get("pair");
    if (pairCode) {
      setInitialPairCode(pairCode.toUpperCase());
      if (!token) {
        setShowLoginModal(true);
      }
    }
  }, [token]);

  // Capture PWA beforeinstallprompt event
  useEffect(() => {
    const handler = (e: any) => {
      e.preventDefault();
      setInstallPromptEvent(e);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const handleInstallPwa = async () => {
    if (!installPromptEvent) return;
    installPromptEvent.prompt();
    const { outcome } = await installPromptEvent.userChoice;
    if (outcome === "accepted") {
      setInstallPromptEvent(null);
    }
  };

  const handleRequestNotifications = async () => {
    if (typeof Notification === "undefined") {
      alert("Notifications are not supported in this browser environment.");
      return;
    }
    const perm = await Notification.requestPermission();
    setNotificationsEnabled(perm === "granted");
  };

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

  // Real-time multi-device sync callbacks
  const handleSessionCreated = useCallback((newSession: Session) => {
    setSessions((prev) => {
      if (prev.some((s) => s.id === newSession.id)) return prev;
      return [newSession, ...prev];
    });
    setActiveSessionId(newSession.id);
  }, []);

  const handleSessionUpdated = useCallback((updated: { id: string; title?: string; updated_at?: string; summary?: string | null }) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === updated.id ? { ...s, ...updated } : s))
    );
  }, []);

  const handleSessionDeleted = useCallback((deletedId: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== deletedId));
    setActiveSessionId((current) => (current === deletedId ? null : current));
  }, []);

  const handleLogout = useCallback(() => {
    clearStoredAuth();
    setToken(null);
    setDevice(null);
    setSessions([]);
    setActiveSessionId(null);
    setShowLoginModal(true);
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
    onSessionUpdated: handleSessionUpdated,
    onSessionDeleted: handleSessionDeleted,
    onAuthRevoked: handleLogout,
  });

  const handleLoginSuccess = (newToken: string, newDevice: Device) => {
    storeAuth(newToken, newDevice);
    setToken(newToken);
    setDevice(newDevice);
    setShowLoginModal(false);

    // Clean up query param if we logged in via ?pair=
    if (window.location.search.includes("pair=")) {
      const cleanUrl = window.location.pathname;
      window.history.replaceState({}, document.title, cleanUrl);
    }
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
      <LoginModal
        isOpen={showLoginModal}
        initialPairCode={initialPairCode}
        onSuccess={handleLoginSuccess}
      />

      <MemoryModal
        isOpen={isMemoryModalOpen}
        onClose={() => setIsMemoryModalOpen(false)}
        initialTab={memoryInitialTab}
        onSelectSession={setActiveSessionId}
      />

      <DeviceModal
        isOpen={isDeviceModalOpen}
        onClose={() => setIsDeviceModalOpen(false)}
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
        onOpenDevices={() => setIsDeviceModalOpen(true)}
        canInstallPwa={Boolean(installPromptEvent)}
        onInstallPwa={handleInstallPwa}
        notificationsEnabled={notificationsEnabled}
        onRequestNotifications={handleRequestNotifications}
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
