import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Filter,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { api } from "../api";
import { AuditLogEntry } from "../types";

interface AuditLogModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuditLogModal: React.FC<AuditLogModalProps> = ({ isOpen, onClose }) => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchLogs = async () => {
    setIsLoading(true);
    try {
      const data = await api.listAuditLogs(100);
      setLogs(data);
    } catch (err: any) {
      console.error("Failed to load audit logs", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchLogs();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const filteredLogs = logs.filter((log) => {
    if (riskFilter !== "all" && log.risk_level.toLowerCase() !== riskFilter) {
      return false;
    }
    if (statusFilter !== "all" && log.status.toLowerCase() !== statusFilter) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTool = log.tool.toLowerCase().includes(q);
      const matchArgs = log.args_json.toLowerCase().includes(q);
      const matchResult = (log.result_json || "").toLowerCase().includes(q);
      const matchError = (log.error || "").toLowerCase().includes(q);
      return matchTool || matchArgs || matchResult || matchError;
    }
    return true;
  });

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === "executed") {
      return (
        <span className="audit-badge audit-badge-executed">
          <CheckCircle2 size={12} />
          <span>Executed</span>
        </span>
      );
    }
    if (s === "pending_approval") {
      return (
        <span className="audit-badge audit-badge-pending">
          <Clock size={12} />
          <span>Pending</span>
        </span>
      );
    }
    if (s === "denied") {
      return (
        <span className="audit-badge audit-badge-denied">
          <XCircle size={12} />
          <span>Denied</span>
        </span>
      );
    }
    if (s === "killed") {
      return (
        <span className="audit-badge audit-badge-killed">
          <AlertCircle size={12} />
          <span>Killed</span>
        </span>
      );
    }
    return (
      <span className="audit-badge audit-badge-failed">
        <AlertCircle size={12} />
        <span>Failed</span>
      </span>
    );
  };

  const getRiskBadge = (risk: string) => {
    const r = risk.toLowerCase();
    return <span className={`audit-risk-badge audit-risk-${r}`}>{risk.toUpperCase()}</span>;
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-card audit-modal-card">
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div className="audit-header-icon">
              <ShieldCheck size={22} color="#fff" />
            </div>
            <div>
              <h2 className="modal-title">Security & Audit Log</h2>
              <p className="modal-subtitle">
                Immutable audit record of all agent tool actions, approval checks, and execution results.
              </p>
            </div>
          </div>
          <button className="btn-icon" onClick={onClose} title="Close audit log">
            <X size={20} />
          </button>
        </div>

        {/* Filters and search */}
        <div className="audit-filters-bar">
          <div className="audit-search-input-wrapper">
            <Search size={15} className="audit-search-icon" />
            <input
              type="text"
              placeholder="Search by tool, argument, or result..."
              className="audit-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div className="audit-select-wrapper">
              <Filter size={13} style={{ opacity: 0.7 }} />
              <select
                value={riskFilter}
                onChange={(e) => setRiskFilter(e.target.value)}
                className="audit-select"
              >
                <option value="all">All Risks</option>
                <option value="low">Low Risk</option>
                <option value="medium">Medium Risk</option>
                <option value="high">High Risk</option>
              </select>
            </div>

            <div className="audit-select-wrapper">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="audit-select"
              >
                <option value="all">All Statuses</option>
                <option value="executed">Executed</option>
                <option value="pending_approval">Pending</option>
                <option value="denied">Denied</option>
                <option value="failed">Failed</option>
                <option value="killed">Killed</option>
              </select>
            </div>

            <button
              className="btn btn-secondary btn-icon"
              title="Refresh audit log"
              onClick={fetchLogs}
              disabled={isLoading}
            >
              <RefreshCw size={14} className={isLoading ? "spin" : ""} />
            </button>
          </div>
        </div>

        {/* Log Entries List */}
        <div className="audit-list-container">
          {filteredLogs.length === 0 ? (
            <div className="audit-empty-state">
              <ShieldCheck size={36} style={{ opacity: 0.3, marginBottom: 8 }} />
              <p>No audit entries match the current filters.</p>
            </div>
          ) : (
            <div className="audit-table">
              <div className="audit-table-header">
                <span style={{ width: "15%" }}>Time</span>
                <span style={{ width: "25%" }}>Tool</span>
                <span style={{ width: "15%" }}>Risk</span>
                <span style={{ width: "20%" }}>Status</span>
                <span style={{ width: "15%" }}>Approved By</span>
                <span style={{ width: "10%", textAlign: "right" }}>Details</span>
              </div>

              {filteredLogs.map((log) => {
                const isExpanded = expandedId === log.id;
                let parsedArgs = null;
                let parsedResult = null;
                try {
                  parsedArgs = JSON.parse(log.args_json);
                } catch {
                  parsedArgs = log.args_json;
                }
                if (log.result_json) {
                  try {
                    parsedResult = JSON.parse(log.result_json);
                  } catch {
                    parsedResult = log.result_json;
                  }
                }

                return (
                  <div key={log.id} className="audit-row-container">
                    <div
                      className={`audit-row ${isExpanded ? "expanded" : ""}`}
                      onClick={() => setExpandedId(isExpanded ? null : log.id)}
                    >
                      <span className="audit-cell-time" style={{ width: "15%" }}>
                        {new Date(log.ts).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        })}
                      </span>
                      <span className="audit-cell-tool" style={{ width: "25%" }}>
                        <code>{log.tool}</code>
                      </span>
                      <span style={{ width: "15%" }}>{getRiskBadge(log.risk_level)}</span>
                      <span style={{ width: "20%" }}>{getStatusBadge(log.status)}</span>
                      <span className="audit-cell-approver" style={{ width: "15%" }}>
                        {log.approved_by || "—"}
                      </span>
                      <span style={{ width: "10%", textAlign: "right" }}>
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </span>
                    </div>

                    {isExpanded && (
                      <div className="audit-expanded-details">
                        <div className="audit-details-section">
                          <h4>Arguments</h4>
                          <pre>
                            <code>
                              {typeof parsedArgs === "object"
                                ? JSON.stringify(parsedArgs, null, 2)
                                : parsedArgs}
                            </code>
                          </pre>
                        </div>

                        {parsedResult && (
                          <div className="audit-details-section">
                            <h4>Execution Result</h4>
                            <pre>
                              <code>
                                {typeof parsedResult === "object"
                                  ? JSON.stringify(parsedResult, null, 2)
                                  : parsedResult}
                              </code>
                            </pre>
                          </div>
                        )}

                        {log.error && (
                          <div className="audit-details-section audit-error-box">
                            <h4>Error</h4>
                            <pre>
                              <code>{log.error}</code>
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
