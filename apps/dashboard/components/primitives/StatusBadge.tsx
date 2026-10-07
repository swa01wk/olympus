import { presentationForUiKey } from "@/src/adapters/status";
import { cn } from "@/lib/utils";

export type StatusBadgeProps = {
  /** UI status key (from mapBackendStatus) or raw key from STATUS vocabulary */
  status: string;
  label?: string;
  size?: "sm";
};

export function StatusBadge({ status, label, size }: StatusBadgeProps) {
  const meta = presentationForUiKey(status);
  return (
    <span
      className={cn("ol-chip", `ol-tone-${meta.tone}`, size === "sm" && "ol-chip-sm")}
      data-status={status}
    >
      <span className="ol-chip-g" aria-hidden="true">
        {meta.glyph}
      </span>
      <span>{label ?? meta.label}</span>
    </span>
  );
}
