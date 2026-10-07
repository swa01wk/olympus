import type { DeliveryCycleType } from "@/src/api/types/core";

const LABELS: Record<DeliveryCycleType, { name: string; direction: string }> = {
  GREENFIELD_BUILD: { name: "Greenfield build", direction: "New product from source" },
  BROWNFIELD_ONBOARDING: { name: "Brownfield onboarding", direction: "Recover and baseline existing code" },
  FEATURE_CHANGE: { name: "Feature change", direction: "Change on ready project" },
  BUG_FIX: { name: "Bug fix", direction: "Repair defect with reproduction trail" },
  REMEDIATION: { name: "Remediation", direction: "Readiness remediation cycle" },
};

export function journeyLabel(type: DeliveryCycleType): string {
  return LABELS[type]?.name ?? type;
}

export function journeyDirection(type: DeliveryCycleType): string {
  return LABELS[type]?.direction ?? "";
}
