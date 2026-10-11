import { useCallback, useEffect, useRef, useState } from "react";
import { Message, Session, WsServerEvent } from "../types";
import { api, getStoredToken } from "../api";

interface UseChatProps {
  activeSessionId: string | null;
  onSessionCreated?: (session: Session) => void;
  onSessionUpdated?: (session: { id: string; title?: string; updated_at?: string; summary?: string | null }) => void;
  onSessionDeleted?: (sessionId: string) => void;
  onAuthRevoked?: () => void;
  onPendingActionCreated?: (action: any) => void;
  onPendingActionResolved?: (actionId: string, status: string) => void;
  onAgentKilled?: () => void;
  onReminderFired?: (reminder: any) => void;
  onDailyBriefing?: (briefing: any) => void;
  onMessageCompleted?: (message: Message) => void;
}


export function useChat({
  activeSessionId,
  onSessionCreated,
  onSessionUpdated,
  onSessionDeleted,
  onAuthRevoked,
  onPendingActionCreated,
  onPendingActionResolved,
  onAgentKilled,
  onReminderFired,
  onDailyBriefing,
  onMessageCompleted,
}: UseChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingContent, setStreamingContent] = useState<string>("");
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  // Inform server when activeSessionId changes
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "select_session",
          session_id: activeSessionId,
        })
      );
    }
  }, [activeSessionId]);

  // Load message history when activeSessionId changes
  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      setStreamingContent("");
      setIsStreaming(false);
      return;
    }

    let isMounted = true;
    api
      .listMessages(activeSessionId)
      .then((history) => {
        if (isMounted) {
          setMessages(history);
          setStreamingContent("");
          setIsStreaming(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setErrorMessage(err.message);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [activeSessionId]);

  // Connect WebSocket
  const connectWs = useCallback(() => {
    const token = getStoredToken();
    if (!token) {
      setIsConnected(false);
      return;
    }

    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/chat?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setErrorMessage(null);
      // Synchronize currently selected session upon connection
      if (activeSessionId) {
        ws.send(
          JSON.stringify({
            type: "select_session",
            session_id: activeSessionId,
          })
        );
      }
    };

    ws.onmessage = (event) => {
      try {
        const data: WsServerEvent = JSON.parse(event.data);

        switch (data.type) {
          case "connected":
            setIsConnected(true);
            break;

          case "message_saved":
            if (data.session_id === activeSessionId) {
              setMessages((prev) => {
                if (prev.some((m) => m.id === data.message.id || (m.role === data.message.role && m.content === data.message.content))) {
                  return prev.map((m) => (m.content === data.message.content && m.id.startsWith("temp-") ? data.message : m));
                }
                return [...prev, data.message];
              });
              if (data.message.role === "user") {
                setIsStreaming(true);
                setStreamingContent("");
              }
            }
            break;

          case "token":
            if (data.session_id === activeSessionId) {
              setIsStreaming(true);
              setStreamingContent((prev) => prev + data.delta);
            }
            break;

          case "done":
            if (data.session_id === activeSessionId) {
              setIsStreaming(false);
              setStreamingContent("");
              setMessages((prev) => {
                const filtered = prev.filter((m) => !m.id.startsWith("temp-"));
                if (filtered.some((m) => m.id === data.message.id)) {
                  return filtered;
                }
                return [...filtered, data.message];
              });

              // Trigger background push notification if window is minimized/hidden
              if (
                typeof document !== "undefined" &&
                document.hidden &&
                typeof Notification !== "undefined" &&
                Notification.permission === "granted"
              ) {
                try {
                  new Notification("Aria", {
                    body: data.message.content.slice(0, 120) + (data.message.content.length > 120 ? "..." : ""),
                    icon: "/icons/icon-192.svg",
                  });
                } catch {
                  // Ignore notification error on un-supported environments
                }
              }

              onMessageCompleted?.(data.message);
            }
            break;

          case "reminder_fired":
            onReminderFired?.(data.reminder);
            if (
              typeof Notification !== "undefined" &&
              Notification.permission === "granted"
            ) {
              try {
                new Notification("⏰ Reminder Due", {
                  body: data.reminder.text,
                  icon: "/icons/icon-192.svg",
                });
              } catch {}
            }
            break;

          case "daily_briefing":
            onDailyBriefing?.(data.briefing);
            if (
              typeof Notification !== "undefined" &&
              Notification.permission === "granted"
            ) {
              try {
                new Notification("☀️ Morning Briefing", {
                  body: data.briefing.content.slice(0, 100),
                  icon: "/icons/icon-192.svg",
                });
              } catch {}
            }
            break;

          case "session_created":
            onSessionCreated?.(data.session);
            break;

          case "session_updated":
            onSessionUpdated?.(data.session);
            break;

          case "session_deleted":
            onSessionDeleted?.(data.session_id);
            break;

          case "auth_revoked":
            setIsConnected(false);
            setErrorMessage("Device access has been revoked by the owner.");
            onAuthRevoked?.();
            break;

          case "pending_action_created":
            onPendingActionCreated?.(data.action);
            break;

          case "pending_action_resolved":
            onPendingActionResolved?.(data.action_id, data.status);
            break;

          case "agent_killed":
            onAgentKilled?.();
            break;

          case "error":
            setIsStreaming(false);
            setStreamingContent("");
            setErrorMessage(data.error);
            break;
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      wsRef.current = null;
      // Reconnect after 3 seconds if token exists
      if (getStoredToken()) {
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connectWs();
        }, 3000);
      }
    };

    ws.onerror = () => {
      setIsConnected(false);
    };
  }, [
    activeSessionId,
    onAgentKilled,
    onAuthRevoked,
    onDailyBriefing,
    onMessageCompleted,
    onPendingActionCreated,
    onPendingActionResolved,
    onReminderFired,
    onSessionCreated,
    onSessionDeleted,
    onSessionUpdated,
  ]);


  useEffect(() => {
    connectWs();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connectWs]);

  // Action / Kill helpers over WebSocket
  const sendApproveAction = useCallback((actionId: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "action_approve", action_id: actionId }));
    }
  }, []);

  const sendRejectAction = useCallback((actionId: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "action_reject", action_id: actionId }));
    }
  }, []);

  const sendKill = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "kill" }));
    }
  }, []);

  // Send a message
  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) return;

      setErrorMessage(null);

      let targetSessionId = activeSessionId;

      // If no session exists, create one first
      if (!targetSessionId) {
        try {
          const newSession = await api.createSession(trimmed.slice(0, 32));
          targetSessionId = newSession.id;
          if (onSessionCreated) {
            onSessionCreated(newSession);
          }
        } catch (err: any) {
          setErrorMessage(err.message || "Failed to create new session");
          return;
        }
      }

      // Optimistically show user message
      const tempUserMsg: Message = {
        id: `temp-${Date.now()}`,
        session_id: targetSessionId,
        role: "user",
        content: trimmed,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempUserMsg]);
      setIsStreaming(true);
      setStreamingContent("");

      // Send through WebSocket if open
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: "message",
            session_id: targetSessionId,
            content: trimmed,
          })
        );
      } else {
        setErrorMessage("Connection to local agent is offline. Reconnecting...");
        connectWs();
      }
    },
    [activeSessionId, connectWs, onSessionCreated]
  );

  return {
    messages,
    streamingContent,
    isStreaming,
    isConnected,
    errorMessage,
    sendMessage,
    setErrorMessage,
    sendApproveAction,
    sendRejectAction,
    sendKill,
  };
}
