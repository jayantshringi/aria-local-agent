import React, { useState } from "react";
import { OctagonAlert, RotateCcw } from "lucide-react";
import { api } from "../api";
import { KillSwitchStatus } from "../types";

interface KillSwitchButtonProps {
  status: KillSwitchStatus;
  onStatusChange: (status: KillSwitchStatus) => void;
  onKilled?: () => void;
}

export const KillSwitchButton: React.FC<KillSwitchButtonProps> = ({
  status,
  onStatusChange,
  onKilled,
}) => {
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleTriggerKill = async () => {
    if (
      !confirm(
        "EMERGENCY KILL SWITCH: Are you sure you want to halt all active agent tasks and abort all pending actions immediately?"
      )
    ) {
      return;
    }

    setIsLoading(true);
    try {
      await api.triggerKillSwitch();
      onStatusChange({ active: true, triggered_at: new Date().toISOString() });
      onKilled?.();
    } catch (err: any) {
      alert(`Failed to activate kill switch: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = async () => {
    setIsLoading(true);
    try {
      await api.resetKillSwitch();
      onStatusChange({ active: false, triggered_at: null });
    } catch (err: any) {
      alert(`Failed to reset kill switch: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  if (status.active) {
    return (
      <div className="kill-switch-active-banner">
        <div className="kill-switch-indicator">
          <span className="kill-switch-pulse" />
          <OctagonAlert size={16} />
          <span className="kill-switch-text">AGENT HALTED (KILL SWITCH ACTIVE)</span>
        </div>
        <button
          className="btn btn-sm btn-kill-reset"
          onClick={handleReset}
          disabled={isLoading}
          title="Reset emergency stop and resume normal operation"
        >
          <RotateCcw size={13} />
          <span>Reset</span>
        </button>
      </div>
    );
  }

  return (
    <button
      className="btn btn-sm btn-kill-trigger"
      onClick={handleTriggerKill}
      disabled={isLoading}
      title="Emergency Kill Switch: immediately halts execution and cancels pending actions"
    >
      <OctagonAlert size={14} />
      <span>Kill Switch</span>
    </button>
  );
};
