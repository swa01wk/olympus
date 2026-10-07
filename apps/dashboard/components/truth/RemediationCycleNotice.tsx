"use client";

import { ExceptionState } from "@/components/truth/ExceptionState";

/** G10: fifth journey not in design pack — honest empty guidance. */
export function RemediationCycleNotice() {
  return (
    <ExceptionState
      status="pending"
      statusLabel="Remediation journey"
      reason="This cycle type is supported by the Control API but not fully mapped in the operator design pack."
      consequence="Use the control-plane map and drill-downs; lane copy may be generic."
    />
  );
}
