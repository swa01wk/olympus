"use client";

import { ModalDialog } from "@/components/dialogs/ModalDialog";
import { Button } from "@/components/primitives";
import { previewCreateCycle } from "@/lib/command-preview";
import { newIdempotencyKey } from "@/lib/utils";
import { createDeliveryCycleCommand } from "@/src/api/commands";
import { cn } from "@/lib/utils";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { cycleMapPath } from "@/lib/cycle-url";

const JOURNEYS = {
  GF: { label: "Greenfield Build", type: "GREENFIELD_BUILD" },
  BF: { label: "Brownfield Onboarding", type: "BROWNFIELD_ONBOARDING" },
  FC: { label: "Feature Change", type: "FEATURE_CHANGE" },
  BG: { label: "Bug Fix", type: "BUG_FIX" },
} as const;

type JourneyKey = keyof typeof JOURNEYS;

export function IntakeFormDialog({
  open,
  projectId,
  onClose,
}: {
  open: boolean;
  projectId: string | null;
  onClose: () => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [journey, setJourney] = useState<JourneyKey>("FC");
  const [objective, setObjective] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const meta = JOURNEYS[journey];

  const submit = async () => {
    if (!projectId || !objective.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const cycle = await createDeliveryCycleCommand(
        projectId,
        meta.type,
        objective.trim(),
        null,
        newIdempotencyKey(),
      );
      await queryClient.invalidateQueries({ queryKey: ["delivery-cycles", projectId] });
      onClose();
      setObjective("");
      router.push(cycleMapPath(projectId, cycle.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create cycle failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalDialog
      open={open && Boolean(projectId)}
      onClose={onClose}
      label="New delivery cycle"
      title="Intent-specific intake"
      wide
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={!objective.trim() || busy} onClick={submit}>
            Create delivery cycle
          </Button>
        </>
      }
    >
      <div className="ol-appr">
        <div className="ol-seg ol-seg-wide" role="radiogroup" aria-label="Journey">
          {(Object.keys(JOURNEYS) as JourneyKey[]).map((id) => (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={journey === id}
              className={cn("ol-seg-i", journey === id && "is-on")}
              onClick={() => setJourney(id)}
            >
              {JOURNEYS[id].label}
            </button>
          ))}
        </div>
        <label className="ol-field">
          <span className="ol-label">Objective</span>
          <textarea
            rows={4}
            value={objective}
            onChange={(ev) => setObjective(ev.target.value)}
            placeholder="What this delivery cycle must achieve — stored as cycle objective."
          />
        </label>
        {projectId && (
          <code className="ol-cmd-api">
            {previewCreateCycle(projectId, meta.type, objective)}
          </code>
        )}
        {error && (
          <div className="ol-sent" role="alert">
            {error}
          </div>
        )}
      </div>
    </ModalDialog>
  );
}
