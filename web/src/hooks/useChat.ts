import { useCallback, useEffect, useRef, useState } from "react";
import { Message, Session, WsServerEvent } from "../types";
import { api, getStoredToken } from "../api";

interface UseChatProps {
  activeSessionId: string | null;
  onSessionCreated?: (session: Session) => void;
}

export function useChat({ activeSessionId, onSessionCreated }: UseChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingContent, setStreamingContent] = useState<string>("");
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

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

    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
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
    };

    ws.onmessage = (event) => {
      try {
        const data: WsServerEvent = JSON.parse(event.data);

        switch (data.type) {
          case "connected":
            setIsConnected(true);
            break;

          case "message_saved":
            if (data.message.role === "user") {
              setMessages((prev) => {
                if (prev.some((m) => m.id === data.message.id)) return prev;
                return [...prev, data.message];
              });
            }
            break;

          case "token":
            setIsStreaming(true);
            setStreamingContent((prev) => prev + data.delta);
            break;

          case "done":
            setIsStreaming(false);
            setStreamingContent("");
            setMessages((prev) => [...prev, data.message]);
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
  }, []);

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
  };
}
