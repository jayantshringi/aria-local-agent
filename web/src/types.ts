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
  | { type: "auth"; token: string }
  | { type: "action_approve"; action_id: string }
  | { type: "action_reject"; action_id: string }
  | { type: "kill" }
  | { type: "execute_tool"; tool: string; args?: Record<string, any>; session_id?: string };

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
  | { type: "pong" }
  | {
      type: "pending_action_created";
      action: {
        id: string;
        session_id?: string | null;
        tool: string;
        args: Record<string, any>;
        risk_level: "low" | "medium" | "high";
        created_at: string;
      };
    }
  | {
      type: "pending_action_resolved";
      action_id: string;
      status: string;
      resolved_by?: string;
      result?: any;
    }
  | { type: "agent_killed"; killed_actions?: any[] }
  | { type: "action_result"; result: any }
  | { type: "tool_dispatched"; session_id?: string; tool?: string; result: any }
  | { type: "reminder_fired"; reminder: Reminder }
  | { type: "daily_briefing"; briefing: DailyBriefing };

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

// Phase 4 Agent & Safety Types
export interface AgentTool {
  name: string;
  description: string;
  risk_level: "low" | "medium" | "high";
  parameters: Record<string, any>;
}

export interface PendingAction {
  id: string;
  tool: string;
  args_json: string;
  risk_level: "low" | "medium" | "high";
  session_id?: string | null;
  status: "pending" | "approved" | "rejected" | "killed" | "failed";
  created_at: string;
  resolved_at?: string | null;
  resolved_by?: string | null;
}

export interface AuditLogEntry {
  id: string;
  ts: string;
  tool: string;
  args_json: string;
  risk_level: string;
  status: string;
  approved_by?: string | null;
  result_json?: string | null;
  error?: string | null;
}

export interface KillSwitchStatus {
  active: boolean;
  triggered_at: string | null;
}

// Phase 5 Voice & Scheduler Types
export interface Reminder {
  id: string;
  text: string;
  due_at: string;
  repeat_rule?: string | null;
  status: "pending" | "completed" | "cancelled";
  created_at: string;
}

export interface DailyBriefing {
  date: string;
  timestamp: string;
  content: string;
  language: string;
  reminders_count: number;
  pending_actions_count: number;
  yesterday_sessions_count: number;
}

export interface VoiceStatus {
  stt_available: boolean;
  stt_model: string;
  tts_available: boolean;
  tts_model: string;
  language: string;
}

export interface TranscribeResponse {
  text: string;
  metadata: {
    language: string;
    language_probability: number;
    duration: number;
    segments: Array<{ start: number; end: number; text: string }>;
  };
}

// Phase 6 System & Telemetry Types
export interface SystemTelemetry {
  cpu: {
    percent: number;
    cores: number;
  };
  memory: {
    total_bytes: number;
    used_bytes: number;
    available_bytes: number;
    percent: number;
  };
  disk: {
    total_bytes: number;
    used_bytes: number;
    free_bytes: number;
    percent: number;
    path: string;
  };
  platform: {
    os: string;
    release: string;
    arch: string;
    python: string;
  };
  uptime_seconds: number;
  embedding_cache: {
    size: number;
    capacity: number;
    hits: number;
    misses: number;
    hit_rate: number;
  };
}

export interface OllamaModelInfo {
  name: string;
  size: number;
  modified_at: string;
  parameter_size: string;
  quantization_level: string;
  family: string;
}

export interface SystemModelsResponse {
  active_chat_model: string;
  configured_embed_model: string;
  ollama_online: boolean;
  models: OllamaModelInfo[];
}

export interface SystemPluginsResponse {
  plugins_dir: string;
  registered_tools_count: number;
  tools: AgentTool[];
}


