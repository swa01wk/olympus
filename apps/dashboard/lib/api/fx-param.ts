import type { ScenarioId } from "@/lib/api/scenario-controller";

export const DEFAULT_SCENARIO: ScenarioId = "feature-change";
export const DEFAULT_CHECKPOINT_ID = "05-development-running";

const SCENARIOS: ScenarioId[] = ["greenfield", "brownfield", "feature-change", "bug-fix"];

/** Checkpoint ids are validated at runtime via dynamic import in fixture mode. */
export function parseFxParam(raw: string | null | undefined): {
  scenarioId: ScenarioId;
  checkpointId: string;
} | null {
  if (!raw?.includes(":")) return null;
  const [scenario, checkpointId] = raw.split(":", 2);
  if (!SCENARIOS.includes(scenario as ScenarioId)) return null;
  if (!checkpointId) return null;
  return { scenarioId: scenario as ScenarioId, checkpointId };
}

export function formatFxParam(scenarioId: ScenarioId, checkpointId: string): string {
  return `${scenarioId}:${checkpointId}`;
}

export const FX_SESSION_KEY = "olympus.fx";
