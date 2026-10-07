"use client";

import type { ReactNode } from "react";

/** Shared workspace chrome; decision / next step live in StudioShell (C5). */
export function StageWorkspaceFrame({
  decision,
  children,
  nextStep,
}: {
  decision?: ReactNode;
  children: ReactNode;
  nextStep?: ReactNode;
}) {
  return (
    <div className="ol-ws-frame">
      {decision && <div className="ol-ws-decision-slot">{decision}</div>}
      <div className="ol-ws-body">{children}</div>
      {nextStep && <div className="ol-ws-next-slot">{nextStep}</div>}
    </div>
  );
}
