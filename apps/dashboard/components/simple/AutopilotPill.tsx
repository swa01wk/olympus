import type { AutopilotStatus } from "@/src/api/types/autopilot";

const LABELS: Record<AutopilotStatus, string> = {
  OFF: "Paused",
  WORKING: "Working",
  NEEDS_YOU: "Needs you",
  BLOCKED: "Stopped",
  DONE: "Done",
};

export function AutopilotPill({ status }: { status: AutopilotStatus }) {
  return (
    <span className="sp-pill" data-status={status}>
      {LABELS[status] ?? status}
    </span>
  );
}
