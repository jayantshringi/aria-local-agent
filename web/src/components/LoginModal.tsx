import React, { useEffect, useState } from "react";
import { KeyRound, QrCode, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { Device } from "../types";

interface LoginModalProps {
  isOpen: boolean;
  initialPairCode?: string | null;
  onSuccess: (token: string, device: Device) => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({
  isOpen,
  initialPairCode,
  onSuccess,
}) => {
  const [mode, setMode] = useState<"pair" | "password">("password");
  const [password, setPassword] = useState("");
  const [pairingCode, setPairingCode] = useState(initialPairCode || "");
  const [deviceName, setDeviceName] = useState(
    navigator.userAgent.includes("Mobile")
      ? "Mobile Phone"
      : navigator.userAgent.includes("Mac")
      ? "MacBook"
      : "Desktop PC"
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialPairCode) {
      setPairingCode(initialPairCode);
      setMode("pair");
    }
  }, [initialPairCode]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (mode === "pair") {
        if (!pairingCode.trim()) {
          setError("Please enter a valid pairing code");
          setLoading(false);
          return;
        }
        const res = await api.claimPairingCode(pairingCode.trim().toUpperCase(), deviceName);
        onSuccess(res.token, res.device);
      } else {
        if (!password) {
          setError("Please enter your master password");
          setLoading(false);
          return;
        }
        const res = await api.login(password, deviceName);
        onSuccess(res.token, res.device);
      }
    } catch (err: any) {
      setError(
        err.message ||
          (mode === "pair"
            ? "Invalid or expired pairing code. Please generate a new code on your host PC."
            : "Authentication failed. Check your password.")
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content auth-modal">
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <div className="brand-logo" style={{ width: 40, height: 40 }}>
            <ShieldCheck size={24} color="#fff" />
          </div>
          <div>
            <h2 className="modal-title">Authenticate Aria</h2>
            <div className="brand-badge">Local-First Vault</div>
          </div>
        </div>

        {/* Tab switch between Pair with Code and Master Password */}
        <div className="modal-tabs" style={{ marginBottom: "16px" }}>
          <button
            type="button"
            className={`modal-tab ${mode === "pair" ? "active" : ""}`}
            onClick={() => {
              setMode("pair");
              setError(null);
            }}
          >
            Pair with Code
          </button>
          <button
            type="button"
            className={`modal-tab ${mode === "password" ? "active" : ""}`}
            onClick={() => {
              setMode("password");
              setError(null);
            }}
          >
            Master Password
          </button>
        </div>

        <p className="modal-subtitle">
          {mode === "pair"
            ? "Connect this device using a temporary one-time code generated from your authenticated PC."
            : "Enter your master password. If this is a fresh setup, the password entered here will initialize your vault."}
        </p>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          {mode === "pair" ? (
            <div className="form-group">
              <label className="form-label">Pairing Code</label>
              <input
                type="text"
                className="form-input code-input"
                placeholder="ARIA-XXXX"
                value={pairingCode}
                onChange={(e) => setPairingCode(e.target.value.toUpperCase())}
                required
                autoFocus
                maxLength={12}
                style={{
                  fontFamily: "var(--font-mono)",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  fontSize: "1.1rem",
                }}
              />
              <span className="form-help-text">
                Generate this code on your computer via <strong>Sidebar &gt; Devices</strong>.
              </span>
            </div>
          ) : (
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
          )}

          <div className="form-group">
            <label className="form-label">Device Name</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. My Phone, Living Room Tablet..."
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%", padding: "12px", marginTop: "8px" }}
            disabled={loading || (mode === "pair" ? !pairingCode.trim() : !password)}
          >
            {mode === "pair" ? <QrCode size={16} /> : <KeyRound size={16} />}
            <span>
              {loading
                ? "Connecting..."
                : mode === "pair"
                ? "Pair This Device"
                : "Unlock Vault"}
            </span>
          </button>
        </form>
      </div>
    </div>
  );
};
