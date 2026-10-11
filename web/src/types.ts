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

export interface DeviceRecord {
  id: string;
  name: string;
  created_at: string;
  last_seen: string;
  revoked: number;
}

export interface PairingSession {
  id: string;
  code: string;
  expires_at: string;
  ttl_seconds: number;
  qr_url: string;
}

export type WsClientEvent =
  | { type: "message"; session_id?: string; content: string; model?: string }
  | { type: "select_session"; session_id: string | null }
  | { type: "ping" }
  | { type: "auth"; token: string };

export type WsServerEvent =
  | { type: "connected"; device: { id: string; name: string } }
  | { type: "message_saved"; session_id: string; message: Message }
  | { type: "token"; session_id: string; delta: string }
  | { type: "done"; session_id: string; message: Message }
  | { type: "session_created"; session: Session }
  | { type: "session_updated"; session: { id: string; title?: string; updated_at?: string; summary?: string | null } }
  | { type: "session_deleted"; session_id: string }
  | { type: "auth_revoked"; reason?: string; device_id?: string }
  | { type: "error"; session_id?: string; error: string }
  | { type: "pong" };

export interface ProfileFact {
  id: string;
  key: string;
  value: string;
  status: "pending" | "approved" | "rejected";
  confidence?: number;
  created_at: string;
  updated_at: string;
}

export interface MemorySearchResult {
  text: string;
  source_type: string;
  source_id: string;
  score: number;
  created_at?: string;
}

