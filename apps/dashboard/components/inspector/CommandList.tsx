"use client";

import { Button } from "@/components/primitives";
import { cn } from "@/lib/utils";

export type CommandPreview = {
  label: string;
  cmd: string;
  enabled?: boolean;
  reason?: string;
  /** When set, UI opens confirm dialog before POST. */
  cycleCommand?: { command: string; expectedState: string };
};

export function CommandList({
  cmds,
  onCommand,
}: {
  cmds: CommandPreview[];
  onCommand?: (c: CommandPreview) => void;
}) {
  if (!cmds.length) {
    return <p className="ol-muted ol-small">No operator command is available in this state.</p>;
  }
  return (
    <ul className="ol-cmds">
      {cmds.map((c, i) => (
        <li key={i} className={cn("ol-cmd", c.enabled === false && "is-off")}>
          <Button
            size="sm"
            variant={i === 0 && c.enabled !== false ? "primary" : "quiet"}
            disabled={c.enabled === false}
            title={c.reason}
            onClick={() => onCommand?.(c)}
          >
            {c.label}
          </Button>
          <code className="ol-cmd-api">{c.cmd}</code>
          {c.reason && <span className="ol-cmd-why">{c.reason}</span>}
        </li>
      ))}
    </ul>
  );
}
