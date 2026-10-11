import React, { useEffect, useState } from "react";
import { api, getStoredDevice } from "../api";
import { DeviceRecord, PairingSession } from "../types";

interface DeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DeviceModal: React.FC<DeviceModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<"pair" | "devices">("pair");
  const [pairingSession, setPairingSession] = useState<PairingSession | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState<number>(600);
  const [devices, setDevices] = useState<DeviceRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const currentDevice = getStoredDevice();

  // Load active devices
  const loadDevices = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listDevices();
      setDevices(data);
    } catch (err: any) {
      setError(err.message || "Failed to load registered devices");
    } finally {
      setLoading(false);
    }
  };

  // Generate pairing code
  const generatePairingCode = async () => {
    try {
      setLoading(true);
      setError(null);
      const session = await api.createPairingCode(600);
      setPairingSession(session);
      setSecondsRemaining(session.ttl_seconds || 600);
    } catch (err: any) {
      setError(err.message || "Failed to create pairing session");
    } finally {
      setLoading(false);
    }
  };

  // On open, load devices and create initial pairing code if none
  useEffect(() => {
    if (isOpen) {
      loadDevices();
      if (!pairingSession) {
        generatePairingCode();
      }
    }
  }, [isOpen]);

  // Countdown timer for pairing code
  useEffect(() => {
    if (!isOpen || !pairingSession || secondsRemaining <= 0) return;

    const interval = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [isOpen, pairingSession, secondsRemaining]);

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2500);
  };

  const handleRevoke = async (deviceId: string) => {
    if (!window.confirm("Are you sure you want to revoke access for this device? It will be disconnected immediately.")) {
      return;
    }

    try {
      await api.revokeDevice(deviceId);
      await loadDevices();
    } catch (err: any) {
      setError(err.message || "Failed to revoke device");
    }
  };

  if (!isOpen) return null;

  const formatCountdown = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainder = secs % 60;
    return `${mins.toString().padStart(2, "0")}:${remainder.toString().padStart(2, "0")}`;
  };

  const pairingUrl = pairingSession
    ? `${window.location.origin}/?pair=${pairingSession.code}`
    : "";

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content device-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-badge-icon">📱</div>
            <div>
              <h2>Device Management & Sync</h2>
              <p className="modal-subtitle">Connect phone, tablet, and PC to Aria over your private mesh network</p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} title="Close">
            ✕
          </button>
        </div>

        <div className="modal-tabs">
          <button
            className={`modal-tab ${activeTab === "pair" ? "active" : ""}`}
            onClick={() => setActiveTab("pair")}
          >
            Pair New Device
          </button>
          <button
            className={`modal-tab ${activeTab === "devices" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("devices");
              loadDevices();
            }}
          >
            Connected Devices ({devices.filter((d) => !d.revoked).length})
          </button>
        </div>

        {error && <div className="modal-error-banner">{error}</div>}

        <div className="modal-body">
          {activeTab === "pair" && (
            <div className="pairing-container">
              {pairingSession ? (
                <div className="pairing-layout">
                  <div className="pairing-qr-card">
                    <div className="qr-wrapper">
                      <img
                        src={pairingSession.qr_url}
                        alt={`QR code for ${pairingSession.code}`}
                        className="pairing-qr-img"
                      />
                    </div>
                    <div className="qr-timer">
                      {secondsRemaining > 0 ? (
                        <span>Valid for: <strong>{formatCountdown(secondsRemaining)}</strong></span>
                      ) : (
                        <span className="code-expired">Code expired</span>
                      )}
                    </div>
                  </div>

                  <div className="pairing-details">
                    <div className="pairing-code-display">
                      <div className="pairing-label">One-Time Pairing Code</div>
                      <div className="pairing-code-digits">{pairingSession.code}</div>
                      <div className="pairing-actions">
                        <button
                          className="btn-secondary btn-sm"
                          onClick={() => handleCopy(pairingSession.code, "code")}
                        >
                          {copied === "code" ? "✓ Copied Code" : "Copy Code"}
                        </button>
                        <button
                          className="btn-secondary btn-sm"
                          onClick={() => handleCopy(pairingUrl, "link")}
                        >
                          {copied === "link" ? "✓ Copied Link" : "Copy Direct Link"}
                        </button>
                        <button
                          className="btn-primary btn-sm"
                          onClick={generatePairingCode}
                          disabled={loading}
                        >
                          Generate New
                        </button>
                      </div>
                    </div>

                    <div className="pairing-instructions">
                      <h4>How to pair your phone:</h4>
                      <ol>
                        <li>Make sure your phone is connected to your <strong>Tailscale mesh VPN</strong> or local Wi-Fi.</li>
                        <li>Scan the QR code with your phone camera, or open the link on your phone.</li>
                        <li>Aria will register the phone automatically with a dedicated random device token — <strong>no master password needed on your phone!</strong></li>
                      </ol>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="pairing-loading">
                  <p>Generating secure pairing credentials...</p>
                </div>
              )}
            </div>
          )}

          {activeTab === "devices" && (
            <div className="devices-list-container">
              {loading ? (
                <div className="loading-state">Loading registered devices...</div>
              ) : devices.length === 0 ? (
                <div className="empty-state">No registered devices found.</div>
              ) : (
                <div className="devices-table">
                  {devices.map((dev) => {
                    const isThisDevice = currentDevice?.id === dev.id;
                    const isRevoked = Boolean(dev.revoked);

                    return (
                      <div key={dev.id} className={`device-row ${isRevoked ? "revoked" : ""}`}>
                        <div className="device-info">
                          <div className="device-name-row">
                            <span className="device-icon">{dev.name.toLowerCase().includes("mobile") || dev.name.toLowerCase().includes("phone") ? "📱" : "💻"}</span>
                            <span className="device-name">{dev.name}</span>
                            {isThisDevice && <span className="this-device-badge">Current Device</span>}
                            {isRevoked && <span className="revoked-badge">Revoked</span>}
                          </div>
                          <div className="device-metadata">
                            <span>ID: <code>{dev.id.slice(0, 8)}...</code></span>
                            <span>•</span>
                            <span>Registered: {new Date(dev.created_at).toLocaleDateString()}</span>
                            <span>•</span>
                            <span>Last Seen: {new Date(dev.last_seen).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                        </div>

                        <div className="device-actions">
                          {!isRevoked && !isThisDevice && (
                            <button
                              className="btn-danger btn-sm"
                              onClick={() => handleRevoke(dev.id)}
                            >
                              Revoke Access
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
