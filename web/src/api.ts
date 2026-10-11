import {
  AgentTool,
  AuditLogEntry,
  Device,
  DeviceRecord,
  HealthStatus,
  KillSwitchStatus,
  MemorySearchResult,
  Message,
  PairingSession,
  PendingAction,
  ProfileFact,
  Session,
} from "./types";

const TOKEN_KEY = "aria_device_token";
const DEVICE_KEY = "aria_device_info";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredDevice(): Device | null {
  const raw = localStorage.getItem(DEVICE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Device;
  } catch {
    return null;
  }
}

export function storeAuth(token: string, device: Device): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(DEVICE_KEY, JSON.stringify(device));
}

export function clearStoredAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(DEVICE_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearStoredAuth();
    }
    const errorBody = await response.text();
    let message = `Request failed: ${response.status}`;
    try {
      const parsed = JSON.parse(errorBody);
      if (parsed.detail) message = parsed.detail;
    } catch {
      // use fallback message
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export const api = {
  async getHealth(): Promise<HealthStatus> {
    return request<HealthStatus>("/health");
  },

  async login(password: string, deviceName = "Web Browser") {
    const res = await request<{
      token: string;
      device: Device;
      first_time_setup: boolean;
    }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ password, device_name: deviceName }),
    });
    storeAuth(res.token, res.device);
    return res;
  },

  async listSessions(): Promise<Session[]> {
    return request<Session[]>("/api/v1/sessions");
  },

  async createSession(title = "New Chat"): Promise<Session> {
    return request<Session>("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  },

  async deleteSession(sessionId: string): Promise<void> {
    await request<void>(`/api/v1/sessions/${sessionId}`, {
      method: "DELETE",
    });
  },

  async listMessages(sessionId: string): Promise<Message[]> {
    return request<Message[]>(`/api/v1/sessions/${sessionId}/messages`);
  },

  // Memory & Profile Facts (Phase 2)
  async searchMemory(query: string, limit = 5): Promise<MemorySearchResult[]> {
    const encoded = encodeURIComponent(query);
    return request<MemorySearchResult[]>(`/api/v1/memory/search?q=${encoded}&limit=${limit}`);
  },

  async listProfileFacts(status?: string): Promise<ProfileFact[]> {
    const path = status ? `/api/v1/memory/facts?status=${encodeURIComponent(status)}` : "/api/v1/memory/facts";
    return request<ProfileFact[]>(path);
  },

  async createProfileFact(key: string, value: string, status = "approved"): Promise<ProfileFact> {
    return request<ProfileFact>("/api/v1/memory/facts", {
      method: "POST",
      body: JSON.stringify({ key, value, status }),
    });
  },

  async updateProfileFact(factId: string, status?: string, value?: string): Promise<ProfileFact> {
    return request<ProfileFact>(`/api/v1/memory/facts/${factId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, value }),
    });
  },

  async deleteProfileFact(factId: string): Promise<void> {
    await request<void>(`/api/v1/memory/facts/${factId}`, {
      method: "DELETE",
    });
  },

  async summarizeSession(sessionId: string): Promise<{ session_id: string; summary: string | null }> {
    return request<{ session_id: string; summary: string | null }>(
      `/api/v1/memory/sessions/${sessionId}/summarize`,
      { method: "POST" }
    );
  },

  // Multi-Device & Pairing (Phase 3)
  async listDevices(): Promise<DeviceRecord[]> {
    return request<DeviceRecord[]>("/api/v1/auth/devices");
  },

  async revokeDevice(deviceId: string): Promise<{ revoked: boolean; device_id: string }> {
    return request<{ revoked: boolean; device_id: string }>(
      `/api/v1/auth/devices/${deviceId}/revoke`,
      { method: "POST" }
    );
  },

  async createPairingCode(ttlSeconds = 600): Promise<PairingSession> {
    return request<PairingSession>("/api/v1/auth/pair/create", {
      method: "POST",
      body: JSON.stringify({ ttl_seconds: ttlSeconds }),
    });
  },

  async claimPairingCode(code: string, deviceName = "Mobile Client") {
    const res = await request<{
      token: string;
      device: Device;
      first_time_setup: boolean;
    }>("/api/v1/auth/pair/claim", {
      method: "POST",
      body: JSON.stringify({ code, device_name: deviceName }),
    });
    storeAuth(res.token, res.device);
    return res;
  },

  // Agent Tools & Safety (Phase 4)
  async listTools(): Promise<AgentTool[]> {
    const res = await request<{ count: number; tools: AgentTool[] }>("/api/v1/agent/tools");
    return res.tools;
  },

  async executeTool(tool: string, args: Record<string, any> = {}, sessionId?: string): Promise<any> {
    return request<any>("/api/v1/agent/execute", {
      method: "POST",
      body: JSON.stringify({ tool, args, session_id: sessionId }),
    });
  },

  async listPendingActions(status = "pending"): Promise<PendingAction[]> {
    return request<PendingAction[]>(`/api/v1/agent/actions/pending?status=${encodeURIComponent(status)}`);
  },

  async approveAction(actionId: string): Promise<any> {
    return request<any>(`/api/v1/agent/actions/${actionId}/approve`, {
      method: "POST",
    });
  },

  async rejectAction(actionId: string): Promise<any> {
    return request<any>(`/api/v1/agent/actions/${actionId}/reject`, {
      method: "POST",
    });
  },

  async triggerKillSwitch(): Promise<{ killed_actions: PendingAction[]; active: boolean }> {
    return request<{ killed_actions: PendingAction[]; active: boolean }>("/api/v1/agent/kill", {
      method: "POST",
    });
  },

  async resetKillSwitch(): Promise<{ active: boolean; message: string }> {
    return request<{ active: boolean; message: string }>("/api/v1/agent/kill/reset", {
      method: "POST",
    });
  },

  async getKillSwitchStatus(): Promise<KillSwitchStatus> {
    return request<KillSwitchStatus>("/api/v1/agent/kill/status");
  },

  async listAuditLogs(limit = 100): Promise<AuditLogEntry[]> {
    return request<AuditLogEntry[]>(`/api/v1/agent/audit?limit=${limit}`);
  },
};


