import React, { useEffect, useState } from "react";
import { api } from "../api";
import { AgentTool, OllamaModelInfo, SystemTelemetry } from "../types";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDataWiped?: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  onDataWiped,
}) => {
  const [activeTab, setActiveTab] = useState<
    "models" | "resources" | "plugins" | "backup" | "danger"
  >("models");

  // Models state
  const [activeChatModel, setActiveChatModel] = useState<string>("");
  const [configuredEmbedModel, setConfiguredEmbedModel] = useState<string>("");
  const [modelsList, setModelsList] = useState<OllamaModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [modelSwitching, setModelSwitching] = useState<boolean>(false);
  const [modelMessage, setModelMessage] = useState<string | null>(null);

  // Telemetry state
  const [telemetry, setTelemetry] = useState<SystemTelemetry | null>(null);
  const [loadingTelemetry, setLoadingTelemetry] = useState<boolean>(false);

  // Plugins state
  const [pluginsDir, setPluginsDir] = useState<string>("");
  const [tools, setTools] = useState<AgentTool[]>([]);
  const [rescanning, setRescanning] = useState<boolean>(false);

  // Export / Wipe state
  const [exporting, setExporting] = useState<boolean>(false);
  const [wipeConfirmText, setWipeConfirmText] = useState<string>("");
  const [wiping, setWiping] = useState<boolean>(false);
  const [wipeMessage, setWipeMessage] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  // Load models
  const loadModels = async () => {
    try {
      setError(null);
      const data = await api.getSystemModels();
      setActiveChatModel(data.active_chat_model);
      setConfiguredEmbedModel(data.configured_embed_model);
      setModelsList(data.models);
      setSelectedModel(data.active_chat_model);
    } catch (err: any) {
      setError(err.message || "Failed to load models");
    }
  };

  // Load telemetry
  const loadTelemetry = async () => {
    try {
      setLoadingTelemetry(true);
      setError(null);
      const data = await api.getSystemResources();
      setTelemetry(data);
    } catch (err: any) {
      setError(err.message || "Failed to load telemetry");
    } finally {
      setLoadingTelemetry(false);
    }
  };

  // Load plugins
  const loadPlugins = async () => {
    try {
      setError(null);
      const data = await api.getSystemPlugins();
      setPluginsDir(data.plugins_dir);
      setTools(data.tools);
    } catch (err: any) {
      setError(err.message || "Failed to load plugins");
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadModels();
      loadTelemetry();
      loadPlugins();
      setModelMessage(null);
      setWipeMessage(null);
      setWipeConfirmText("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Handle model switch
  const handleSwitchModel = async () => {
    if (!selectedModel || selectedModel === activeChatModel) return;
    try {
      setModelSwitching(true);
      setModelMessage(null);
      setError(null);
      const res = await api.selectSystemModel(selectedModel);
      setActiveChatModel(res.active_chat_model);
      setModelMessage(`Successfully switched active chat model to ${res.active_chat_model}`);
    } catch (err: any) {
      setError(err.message || "Failed to switch model");
    } finally {
      setModelSwitching(false);
    }
  };

  // Handle JSON export
  const handleExportJson = async () => {
    try {
      setExporting(true);
      const data = await api.exportSystemDataJson();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `aria-backup-${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || "Failed to export JSON data");
    } finally {
      setExporting(false);
    }
  };

  // Handle ZIP export
  const handleExportZip = async () => {
    try {
      setExporting(true);
      const blob = await api.exportSystemDataZip();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `aria-backup-${new Date().toISOString().split("T")[0]}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || "Failed to export ZIP archive");
    } finally {
      setExporting(false);
    }
  };

  // Handle rescan plugins
  const handleRescanPlugins = async () => {
    try {
      setRescanning(true);
      const res = await api.rescanSystemPlugins();
      await loadPlugins();
      setModelMessage(
        res.newly_loaded_plugins.length > 0
          ? `Discovered new plugins: ${res.newly_loaded_plugins.join(", ")}`
          : "Plugin directory rescanned. All plugins up to date."
      );
    } catch (err: any) {
      setError(err.message || "Rescan failed");
    } finally {
      setRescanning(false);
    }
  };

  // Handle permanent wipe
  const handleWipeData = async () => {
    if (wipeConfirmText.trim() !== "PERMANENTLY_DELETE_ALL_DATA") {
      setError("Please type PERMANENTLY_DELETE_ALL_DATA exactly to confirm.");
      return;
    }
    try {
      setWiping(true);
      setError(null);
      await api.wipeSystemData(wipeConfirmText.trim());
      setWipeMessage("All personal agent data was permanently wiped.");
      if (onDataWiped) {
        onDataWiped();
      }
    } catch (err: any) {
      setError(err.message || "Wipe failed");
    } finally {
      setWiping(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes <= 0) return "0 GB";
    const gb = bytes / (1024 * 1024 * 1024);
    return `${gb.toFixed(1)} GB`;
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-container settings-modal-container"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: "720px", width: "95%" }}
      >
        <div className="modal-header">
          <div className="modal-title-wrap">
            <span className="modal-icon">⚙️</span>
            <h2 className="modal-title">System Settings & Polish</h2>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-tabs">
          <button
            className={`modal-tab ${activeTab === "models" ? "active" : ""}`}
            onClick={() => setActiveTab("models")}
          >
            Models
          </button>
          <button
            className={`modal-tab ${activeTab === "resources" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("resources");
              loadTelemetry();
            }}
          >
            Telemetry
          </button>
          <button
            className={`modal-tab ${activeTab === "plugins" ? "active" : ""}`}
            onClick={() => setActiveTab("plugins")}
          >
            Plugins ({tools.length})
          </button>
          <button
            className={`modal-tab ${activeTab === "backup" ? "active" : ""}`}
            onClick={() => setActiveTab("backup")}
          >
            Backup & Export
          </button>
          <button
            className={`modal-tab ${activeTab === "danger" ? "active" : ""}`}
            onClick={() => setActiveTab("danger")}
            style={{ color: "var(--color-danger, #ef4444)" }}
          >
            Danger Zone
          </button>
        </div>

        {error && <div className="modal-error-banner" style={{ margin: "1rem" }}>{error}</div>}
        {modelMessage && (
          <div
            style={{
              margin: "1rem",
              padding: "0.75rem 1rem",
              background: "rgba(16, 185, 129, 0.15)",
              border: "1px solid rgba(16, 185, 129, 0.4)",
              borderRadius: "8px",
              color: "#34d399",
              fontSize: "0.875rem",
            }}
          >
            {modelMessage}
          </div>
        )}

        <div className="modal-body" style={{ maxHeight: "65vh", overflowY: "auto", padding: "1.25rem" }}>
          {/* TAB 1: MODEL SWITCHER */}
          {activeTab === "models" && (
            <div className="settings-section">
              <div style={{ marginBottom: "1.5rem" }}>
                <h3 style={{ fontSize: "1rem", color: "var(--color-text-primary, #fff)", marginBottom: "0.5rem" }}>
                  Active Chat Model
                </h3>
                <p style={{ fontSize: "0.85rem", color: "var(--color-text-secondary, #94a3b8)", marginBottom: "1rem" }}>
                  Select the local Ollama LLM used for generating streaming chat responses.
                </p>

                <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    style={{
                      flex: 1,
                      padding: "0.6rem 0.8rem",
                      background: "rgba(15, 23, 42, 0.8)",
                      border: "1px solid rgba(255, 255, 255, 0.15)",
                      borderRadius: "6px",
                      color: "#fff",
                      fontSize: "0.9rem",
                    }}
                  >
                    {modelsList.length > 0 ? (
                      modelsList.map((m) => (
                        <option key={m.name} value={m.name}>
                          {m.name} ({m.parameter_size || "local"})
                        </option>
                      ))
                    ) : (
                      <option value={activeChatModel}>{activeChatModel} (active)</option>
                    )}
                  </select>

                  <button
                    onClick={handleSwitchModel}
                    disabled={modelSwitching || selectedModel === activeChatModel}
                    className="modal-btn-primary"
                    style={{ padding: "0.6rem 1.25rem", whiteSpace: "nowrap" }}
                  >
                    {modelSwitching ? "Switching..." : "Apply Model"}
                  </button>
                </div>
              </div>

              <div
                style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "8px",
                  padding: "1rem",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                  <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Active Chat Model:</span>
                  <span style={{ color: "#38bdf8", fontWeight: 600, fontSize: "0.85rem" }}>{activeChatModel}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Vector Embeddings Model:</span>
                  <span style={{ color: "#a78bfa", fontWeight: 600, fontSize: "0.85rem" }}>
                    {configuredEmbedModel} (768-dim)
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: SYSTEM TELEMETRY */}
          {activeTab === "resources" && (
            <div className="settings-section">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <span style={{ fontSize: "0.9rem", color: "#94a3b8" }}>Host Hardware Status (100% Offline)</span>
                <button
                  onClick={loadTelemetry}
                  disabled={loadingTelemetry}
                  style={{
                    background: "transparent",
                    border: "1px solid rgba(255, 255, 255, 0.15)",
                    color: "#94a3b8",
                    padding: "0.3rem 0.75rem",
                    borderRadius: "4px",
                    cursor: "pointer",
                    fontSize: "0.8rem",
                  }}
                >
                  {loadingTelemetry ? "Refreshing..." : "↻ Refresh"}
                </button>
              </div>

              {telemetry ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {/* CPU Meter */}
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "1rem", borderRadius: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                      <span style={{ fontSize: "0.85rem", color: "#e2e8f0" }}>
                        CPU Utilization ({telemetry.cpu.cores} cores)
                      </span>
                      <span style={{ fontSize: "0.85rem", color: "#38bdf8", fontWeight: 600 }}>
                        {telemetry.cpu.percent}%
                      </span>
                    </div>
                    <div style={{ height: "6px", background: "rgba(255, 255, 255, 0.1)", borderRadius: "3px", overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.min(100, Math.max(0, telemetry.cpu.percent))}%`,
                          background: "#38bdf8",
                        }}
                      />
                    </div>
                  </div>

                  {/* RAM Meter */}
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "1rem", borderRadius: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                      <span style={{ fontSize: "0.85rem", color: "#e2e8f0" }}>
                        RAM Memory ({formatBytes(telemetry.memory.used_bytes)} / {formatBytes(telemetry.memory.total_bytes)})
                      </span>
                      <span style={{ fontSize: "0.85rem", color: "#10b981", fontWeight: 600 }}>
                        {telemetry.memory.percent}%
                      </span>
                    </div>
                    <div style={{ height: "6px", background: "rgba(255, 255, 255, 0.1)", borderRadius: "3px", overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.min(100, Math.max(0, telemetry.memory.percent))}%`,
                          background: "#10b981",
                        }}
                      />
                    </div>
                  </div>

                  {/* Disk Meter */}
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "1rem", borderRadius: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                      <span style={{ fontSize: "0.85rem", color: "#e2e8f0" }}>
                        Aria Storage Disk ({formatBytes(telemetry.disk.free_bytes)} free)
                      </span>
                      <span style={{ fontSize: "0.85rem", color: "#a855f7", fontWeight: 600 }}>
                        {telemetry.disk.percent}%
                      </span>
                    </div>
                    <div style={{ height: "6px", background: "rgba(255, 255, 255, 0.1)", borderRadius: "3px", overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.min(100, Math.max(0, telemetry.disk.percent))}%`,
                          background: "#a855f7",
                        }}
                      />
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.4rem" }}>
                      Path: {telemetry.disk.path}
                    </div>
                  </div>

                  {/* Embedding Cache Stats */}
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "1rem", borderRadius: "8px" }}>
                    <h4 style={{ fontSize: "0.85rem", color: "#94a3b8", marginBottom: "0.5rem" }}>
                      Embedding Cache Performance
                    </h4>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: "0.8rem" }}>
                      <div>Cached Vectors: <strong style={{ color: "#fff" }}>{telemetry.embedding_cache.size} / {telemetry.embedding_cache.capacity}</strong></div>
                      <div>Hit Rate: <strong style={{ color: "#34d399" }}>{(telemetry.embedding_cache.hit_rate * 100).toFixed(1)}%</strong></div>
                      <div>Total Hits: <strong style={{ color: "#fff" }}>{telemetry.embedding_cache.hits}</strong></div>
                      <div>Total Misses: <strong style={{ color: "#fff" }}>{telemetry.embedding_cache.misses}</strong></div>
                    </div>
                  </div>

                  {/* Platform Info */}
                  <div style={{ fontSize: "0.75rem", color: "#64748b", display: "flex", justifyContent: "space-between" }}>
                    <span>OS: {telemetry.platform.os} {telemetry.platform.release} ({telemetry.platform.arch})</span>
                    <span>Uptime: {Math.floor(telemetry.uptime_seconds / 60)} min</span>
                  </div>
                </div>
              ) : (
                <div style={{ color: "#94a3b8" }}>Loading telemetry...</div>
              )}
            </div>
          )}

          {/* TAB 3: PLUGINS */}
          {activeTab === "plugins" && (
            <div className="settings-section">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <div>
                  <h3 style={{ fontSize: "1rem", color: "#fff" }}>Dynamic Tool Plugins</h3>
                  <p style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Folder: {pluginsDir}</p>
                </div>
                <button
                  onClick={handleRescanPlugins}
                  disabled={rescanning}
                  className="modal-btn-primary"
                  style={{ padding: "0.4rem 0.9rem", fontSize: "0.85rem" }}
                >
                  {rescanning ? "Scanning..." : "Rescan Plugins"}
                </button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {tools.map((t) => (
                  <div
                    key={t.name}
                    style={{
                      background: "rgba(255, 255, 255, 0.03)",
                      border: "1px solid rgba(255, 255, 255, 0.06)",
                      borderRadius: "6px",
                      padding: "0.75rem",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, color: "#38bdf8", fontSize: "0.85rem" }}>
                        {t.name}
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                        {t.description}
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        padding: "0.2rem 0.5rem",
                        borderRadius: "4px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        background:
                          t.risk_level === "high"
                            ? "rgba(239, 68, 68, 0.2)"
                            : t.risk_level === "medium"
                            ? "rgba(234, 179, 8, 0.2)"
                            : "rgba(16, 185, 129, 0.2)",
                        color:
                          t.risk_level === "high"
                            ? "#ef4444"
                            : t.risk_level === "medium"
                            ? "#eab308"
                            : "#10b981",
                      }}
                    >
                      {t.risk_level}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: BACKUP & EXPORT */}
          {activeTab === "backup" && (
            <div className="settings-section">
              <h3 style={{ fontSize: "1rem", color: "#fff", marginBottom: "0.5rem" }}>
                Full Data Export & Portability
              </h3>
              <p style={{ fontSize: "0.85rem", color: "#94a3b8", marginBottom: "1.25rem" }}>
                Download your complete history, session transcripts, memory vectors, profile facts, and notes.
              </p>

              <div style={{ display: "flex", gap: "1rem", marginBottom: "1.5rem" }}>
                <button
                  onClick={handleExportJson}
                  disabled={exporting}
                  className="modal-btn-primary"
                  style={{ flex: 1, padding: "0.75rem" }}
                >
                  {exporting ? "Preparing..." : "📥 Export Full JSON"}
                </button>
                <button
                  onClick={handleExportZip}
                  disabled={exporting}
                  className="modal-btn-primary"
                  style={{ flex: 1, padding: "0.75rem", background: "rgba(168, 85, 247, 0.3)", borderColor: "rgba(168, 85, 247, 0.6)" }}
                >
                  {exporting ? "Preparing..." : "📦 Export Markdown ZIP"}
                </button>
              </div>

              <div
                style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "8px",
                  padding: "1rem",
                }}
              >
                <h4 style={{ fontSize: "0.85rem", color: "#fff", marginBottom: "0.4rem" }}>
                  Encrypted CLI Backup Tool
                </h4>
                <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "0.5rem" }}>
                  Use the AES-256-GCM authenticated backup script for crash-consistent database archives:
                </p>
                <code
                  style={{
                    display: "block",
                    padding: "0.5rem 0.75rem",
                    background: "rgba(0, 0, 0, 0.4)",
                    borderRadius: "4px",
                    fontSize: "0.75rem",
                    color: "#38bdf8",
                  }}
                >
                  python scripts/backup.py backup --output my_backup.aria-bak
                </code>
              </div>
            </div>
          )}

          {/* TAB 5: DANGER ZONE */}
          {activeTab === "danger" && (
            <div className="settings-section">
              <div
                style={{
                  border: "1px solid rgba(239, 68, 68, 0.4)",
                  background: "rgba(239, 68, 68, 0.05)",
                  borderRadius: "8px",
                  padding: "1.25rem",
                }}
              >
                <h3 style={{ fontSize: "1rem", color: "#ef4444", marginBottom: "0.5rem" }}>
                  Permanent Data Deletion
                </h3>
                <p style={{ fontSize: "0.85rem", color: "#cbd5e1", marginBottom: "1rem" }}>
                  This will permanently erase all chat sessions, messages, semantic vectors, profile memories, and audit logs from your local database. Device pairing keys remain enrolled.
                </p>

                {wipeMessage ? (
                  <div style={{ color: "#34d399", fontWeight: 600, padding: "0.5rem 0" }}>
                    ✓ {wipeMessage}
                  </div>
                ) : (
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "0.4rem" }}>
                      Type <strong>PERMANENTLY_DELETE_ALL_DATA</strong> to confirm:
                    </label>
                    <input
                      type="text"
                      value={wipeConfirmText}
                      onChange={(e) => setWipeConfirmText(e.target.value)}
                      placeholder="PERMANENTLY_DELETE_ALL_DATA"
                      style={{
                        width: "100%",
                        padding: "0.6rem 0.8rem",
                        background: "rgba(15, 23, 42, 0.8)",
                        border: "1px solid rgba(239, 68, 68, 0.3)",
                        borderRadius: "6px",
                        color: "#fff",
                        fontSize: "0.85rem",
                        marginBottom: "1rem",
                      }}
                    />
                    <button
                      onClick={handleWipeData}
                      disabled={wiping || wipeConfirmText.trim() !== "PERMANENTLY_DELETE_ALL_DATA"}
                      style={{
                        background: "#ef4444",
                        color: "#fff",
                        border: "none",
                        padding: "0.6rem 1.25rem",
                        borderRadius: "6px",
                        fontWeight: 600,
                        cursor:
                          wipeConfirmText.trim() === "PERMANENTLY_DELETE_ALL_DATA"
                            ? "pointer"
                            : "not-allowed",
                        opacity:
                          wipeConfirmText.trim() === "PERMANENTLY_DELETE_ALL_DATA" ? 1 : 0.5,
                      }}
                    >
                      {wiping ? "Wiping Data..." : "Wipe All User Data"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
