import React, { useState } from "react";
import { KeyRound, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { Device } from "../types";

interface LoginModalProps {
  isOpen: boolean;
  onSuccess: (token: string, device: Device) => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ isOpen, onSuccess }) => {
  const [password, setPassword] = useState("");
  const [deviceName, setDeviceName] = useState(
    navigator.userAgent.includes("Mobile") ? "Phone PWA" : "Primary PC"
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) return;

    setLoading(true);
    setError(null);
    try {
      const res = await api.login(password, deviceName);
      onSuccess(res.token, res.device);
    } catch (err: any) {
      setError(err.message || "Authentication failed. Check your password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <div className="brand-logo" style={{ width: 40, height: 40 }}>
            <ShieldCheck size={24} color="#fff" />
          </div>
          <div>
            <h2 className="modal-title">Authenticate Aria</h2>
            <div className="brand-badge">Local-First Vault</div>
          </div>
        </div>

        <p className="modal-subtitle">
          Enter your master password. If this is your first time starting Aria, the password you enter here will initialize your vault.
        </p>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Master Password</label>
            <input
              type="password"
              className="form-input"
              placeholder="Enter master password..."
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label">Device Name</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. My PC, iPhone..."
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%", padding: "12px", marginTop: "8px" }}
            disabled={loading || !password}
          >
            <KeyRound size={16} />
            <span>{loading ? "Authenticating..." : "Pair Device & Unlock"}</span>
          </button>
        </form>
      </div>
    </div>
  );
};
