import type { ScenarioCheckpointMeta, ScenarioId } from "@/lib/api/scenario-controller";
import type { WorldBuilder } from "./world-builder";

export interface CheckpointDef extends ScenarioCheckpointMeta {
  advancesOn?: { approval_key?: string; command?: string };
  apply?: (builder: WorldBuilder) => void;
}

export type ScenarioCheckpointRegistry = Record<ScenarioId, CheckpointDef[]>;
