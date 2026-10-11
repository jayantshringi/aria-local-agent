import React, { useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  FileCode,
  FolderLock,
  Layers,
  Terminal,
  XCircle,
} from "lucide-react";
import { api } from "../api";
import { PendingAction } from "../types";

interface ActionApprovalBannerProps {
  pendingActions: PendingAction[];
  onActionResolved: (actionId: string, status: string) => void;
  onOpenAuditLog?: () => void;
}

export const ActionApprovalBanner: React.FC<ActionApprovalBannerProps> = ({
  pendingActions,
  onActionResolved,
  onOpenAuditLog,
}) => {
  const [expandedActionId, setExpandedActionId] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);

  if (pendingActions.length === 0) {
    return null;
  }

  const handleApprove = async (action: PendingAction) => {
    setProcessingId(action.id);
    try {
      await api.approveAction(action.id);
      onActionResolved(action.id, "approved");
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (action: PendingAction) => {
    setProcessingId(action.id);
    try {
      await api.rejectAction(action.id);
      onActionResolved(action.id, "rejected");
    } catch (err: any) {
      alert(`Rejection error: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  const getToolIcon = (tool: string) => {
    if (tool.startsWith("files.")) return <FolderLock size={16} />;
    if (tool.startsWith("shell.")) return <Terminal size={16} />;
    if (tool.startsWith("notes.")) return <FileCode size={16} />;
    return <Layers size={16} />;
  };

  return (
    <div className="action-approval-container">
      {pendingActions.map((action) => {
        let parsedArgs: Record<string, any> = {};
        try {
          parsedArgs = JSON.parse(action.args_json);
        } catch {
          // fallback
        }

        const isExpanded = expandedActionId === action.id;
        const isProcessing = processingId === action.id;
        const isHighRisk = action.risk_level === "high";

        return (
          <div
            key={action.id}
            className={`action-approval-card ${isHighRisk ? "high-risk" : "medium-risk"}`}
          >
            <div className="action-card-header">
              <div className="action-card-meta">
                <div className={`action-risk-badge ${action.risk_level}`}>
                  <AlertTriangle size={13} />
                  <span>{action.risk_level.toUpperCase()} RISK</span>
                </div>
                <div className="action-tool-name">
                  {getToolIcon(action.tool)}
                  <span>{action.tool}</span>
                </div>
              </div>

              <div className="action-card-controls">
                <button
                  className="btn-icon"
                  title={isExpanded ? "Collapse arguments" : "Expand arguments"}
                  onClick={() => setExpandedActionId(isExpanded ? null : action.id)}
                >
                  {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
                <button
                  className="btn btn-sm btn-action-reject"
                  onClick={() => handleReject(action)}
                  disabled={isProcessing}
                  title="Reject proposed action"
                >
                  <XCircle size={14} />
                  <span>Deny</span>
                </button>
                <button
                  className="btn btn-sm btn-action-approve"
                  onClick={() => handleApprove(action)}
                  disabled={isProcessing}
                  title="Approve and execute safely"
                >
                  <CheckCircle size={14} />
                  <span>Approve</span>
                </button>
              </div>
            </div>

            <div className="action-args-preview">
              {Object.entries(parsedArgs).length > 0 ? (
                <div className="action-args-chips">
                  {Object.entries(parsedArgs).map(([k, v]) => (
                    <span key={k} className="action-arg-chip">
                      <strong style={{ color: "var(--text-secondary)" }}>{k}:</strong>{" "}
                      <span className="action-arg-val">
                        {typeof v === "object" ? JSON.stringify(v) : String(v)}
                      </span>
                    </span>
                  ))}
                </div>
              ) : (
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  No arguments specified
                </span>
              )}
            </div>

            {isExpanded && (
              <div className="action-args-expanded">
                <pre>
                  <code>{JSON.stringify(parsedArgs, null, 2)}</code>
                </pre>
                {onOpenAuditLog && (
                  <div style={{ marginTop: 8, textAlign: "right" }}>
                    <button
                      className="btn-link"
                      style={{ fontSize: "0.75rem", color: "var(--text-accent)" }}
                      onClick={onOpenAuditLog}
                    >
                      Inspect in Audit Log →
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
