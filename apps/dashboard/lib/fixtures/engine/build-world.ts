import type { ScenarioId } from "@/lib/api/scenario-controller";
import { SCENARIO_CHECKPOINTS } from "../supportdesk/scenarios";
import { cloneWorld } from "./world-builder";
import type { World } from "./world";
import { worldFromLegacyChained } from "./world-from-legacy";
import { applyGreenfieldVariant, applyBrownfieldVariant, applyFeatureChangeIndex, applyBugFixIndex } from "./world-variants";
import { resetClock } from "./clock";
import { enrichCodeModel } from "../supportdesk/code-model/enrich";

const cache = new Map<string, World>();

export function buildWorld(scenarioId: ScenarioId, checkpointIndex: number): World {
  const key = `${scenarioId}:${checkpointIndex}`;
  const cached = cache.get(key);
  if (cached) return cached;

  resetClock(scenarioId === "greenfield" ? "A" : "B", 0);

  let world: World;
  if (scenarioId === "greenfield") {
    world = applyGreenfieldVariant(checkpointIndex);
  } else if (scenarioId === "brownfield") {
    world = applyBrownfieldVariant(checkpointIndex);
  } else if (scenarioId === "feature-change") {
    world = applyFeatureChangeIndex(checkpointIndex);
  } else {
    world = applyBugFixIndex(checkpointIndex);
  }

  enrichCodeModel(world);
  cache.set(key, world);
  return world;
}

export function buildWorldByCheckpointId(scenarioId: ScenarioId, checkpointId: string): World {
  const cps = SCENARIO_CHECKPOINTS[scenarioId];
  const cp = cps.find((c) => c.id === checkpointId) ?? cps[0]!;
  return buildWorld(scenarioId, cp.index);
}

export function clearWorldCache() {
  cache.clear();
}

export function getBaseLegacyWorld(): World {
  return structuredClone(worldFromLegacyChained());
}
