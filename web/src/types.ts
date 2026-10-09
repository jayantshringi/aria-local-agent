export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  summary: string | null;
  device_id?: string | null;
}

export interface Message {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  tokens?: number;
}

export interface Device {
  id: string;
  name: string;
  created_at: string;
}

export interface HealthStatus {
  status: "healthy" | "degraded";
  database: {
    connected: boolean;
    wal_mode: boolean;
  };
  ollama: {
    available: boolean;
    base_url: string;
    configured_chat_model: string;
    configured_embed_model: string;
    chat_model_available: boolean;
    embed_model_available: boolean;
    installed_models: string[];
    error: string | null;
  };
}

export type WsClientEvent =
  | { type: "message"; session_id?: string; content: string; model?: string }
  | { type: "ping" }
  | { type: "auth"; token: string };

export type WsServerEvent =
  | { type: "connected"; device: { id: string; name: string } }
  | { type: "message_saved"; session_id: string; message: Message }
  | { type: "token"; session_id: string; delta: string }
  | { type: "done"; session_id: string; message: Message }
  | { type: "error"; session_id?: string; error: string }
  | { type: "pong" };
