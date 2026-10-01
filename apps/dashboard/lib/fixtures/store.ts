import type { ScenarioId } from "@/lib/api/scenario-controller";
import type { ReleaseEligibilityEvaluation } from "@/lib/contracts/entity-types";
import type { World } from "./engine/world";
import { buildWorld, buildWorldByCheckpointId, clearWorldCache } from "./engine/build-world";
import {
  DEFAULT_CHECKPOINT_ID,
  DEFAULT_SCENARIO,
  SCENARIO_CHECKPOINTS,
} from "./supportdesk/scenarios";
import { createFixtureServicesFromWorld } from "./world-fixture-services";

export type FixtureActorRole = "OPERATOR" | "APPROVER" | "VIEWER";

export interface FixtureStore extends Omit<World, "eligibilityByCycle"> {
  eligibilityByCycle: Map<string, ReleaseEligibilityEvaluation>;
}

let currentWorld: World | null = null;
let currentScenario: ScenarioId = DEFAULT_SCENARIO;
let currentCheckpointId = DEFAULT_CHECKPOINT_ID;

function toStore(world: World): FixtureStore {
  return {
    ...world,
    eligibilityByCycle: new Map(
      world.eligibilityByCycle.map((e) => [e.delivery_cycle_id, e] as const),
    ),
  };
}

export function setFixturePosition(scenarioId: ScenarioId, checkpointId: string) {
  currentScenario = scenarioId;
  currentCheckpointId = checkpointId;
  clearWorldCache();
  currentWorld = buildWorldByCheckpointId(scenarioId, checkpointId);
}

export function getFixtureWorld(): FixtureStore {
  if (!currentWorld) {
    currentWorld = buildWorldByCheckpointId(DEFAULT_SCENARIO, DEFAULT_CHECKPOINT_ID);
  }
  return toStore(currentWorld);
}

export function resetFixtureStore() {
  clearWorldCache();
  currentWorld = null;
  currentScenario = DEFAULT_SCENARIO;
  currentCheckpointId = DEFAULT_CHECKPOINT_ID;
}

/** @deprecated use getFixtureWorld */
export function getFixtureStore(): FixtureStore {
  return getFixtureWorld();
}

export const FIXTURE_DEFAULT_CYCLE_ID = "11111111-1111-4111-8111-111111111203";

export function getFixtureScenarioPosition() {
  const cps = SCENARIO_CHECKPOINTS[currentScenario];
  const cp = cps.find((c) => c.id === currentCheckpointId) ?? cps[0]!;
  return { scenarioId: currentScenario, checkpointId: currentCheckpointId, checkpoint: cp };
}

let servicesCache: ReturnType<typeof createFixtureServicesFromWorld> | null = null;

export function getFixtureServicesForController() {
  const world = getFixtureWorld();
  if (!servicesCache || servicesCache.worldRef !== world) {
    servicesCache = createFixtureServicesFromWorld(world);
  }
  return servicesCache.services;
}

export function appendFixtureEvent(
  partial: Omit<import("@/lib/contracts/entity-types").DomainEvent, "id" | "sequence"> & {
    id?: string;
  },
) {
  const s = getFixtureWorld();
  s.eventSeq += 1;
  const ev = {
    id: partial.id ?? `evt-${s.eventSeq}`,
    sequence: s.eventSeq,
    ...partial,
  };
  s.events.push(ev);
  return ev;
}

/** Default active cycle for demos when none selected. */
export function getDefaultCycleId(): string | null {
  const w = getFixtureWorld();
  const active =
    w.cycles.find((c) => !["COMPLETE", "READY", "CANCELLED", "FAILED"].includes(c.state)) ??
    w.cycles.at(-1);
  return active?.id ?? null;
}
