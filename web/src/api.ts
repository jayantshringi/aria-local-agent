import { Device, HealthStatus, MemorySearchResult, Message, ProfileFact, Session } from "./types";

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
};

