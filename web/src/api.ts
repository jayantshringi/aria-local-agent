import { Device, HealthStatus, Message, Session } from "./types";

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
};
