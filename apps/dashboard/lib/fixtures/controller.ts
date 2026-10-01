import type {
  ScenarioController,
  ScenarioId,
  ScenarioPosition,
} from "@/lib/api/scenario-controller";
import {
  clearWorldCache,
  buildWorldByCheckpointId,
} from "./engine/build-world";
import {
  DEFAULT_CHECKPOINT_ID,
  DEFAULT_SCENARIO,
  SCENARIO_CHECKPOINTS,
} from "./supportdesk/scenarios";
import {
  getFixtureScenarioPosition,
  resetFixtureStore,
  setFixturePosition,
} from "./store";
import { invalidateServicesCache } from "@/lib/api/services";

let playing = false;
let speed = 1;
let playTimer: ReturnType<typeof setInterval> | null = null;
const listeners = new Set<() => void>();

function runtimeFor(scenario: ScenarioId): "A" | "B" {
  return scenario === "greenfield" ? "A" : "B";
}

function positionFromState(): ScenarioPosition {
  const { scenarioId, checkpointId, checkpoint } = getFixtureScenarioPosition();
  const cps = SCENARIO_CHECKPOINTS[scenarioId];
  return {
    scenarioId,
    checkpointId,
    checkpointIndex: checkpoint.index,
    totalCheckpoints: cps.length,
    runtime: runtimeFor(scenarioId),
    meta: checkpoint,
  };
}

function notify() {
  listeners.forEach((l) => l());
}

function applyPosition(scenarioId: ScenarioId, checkpointId: string) {
  setFixturePosition(scenarioId, checkpointId);
  invalidateServicesCache();
  buildWorldByCheckpointId(scenarioId, checkpointId);
  void import("@/lib/events/fixture-stream").then(({ notifyFixtureCheckpointAdvanced }) =>
    notifyFixtureCheckpointAdvanced(),
  );
  notify();
}

function stopPlay() {
  playing = false;
  if (playTimer) clearInterval(playTimer);
  playTimer = null;
}

/** After inbox approval, advance if current checkpoint declares advancesOn.approval_key. */
export function tryAdvanceOnApproval(approvalKey: string) {
  const pos = positionFromState();
  const cps = SCENARIO_CHECKPOINTS[pos.scenarioId];
  const cp = cps.find((c) => c.id === pos.checkpointId);
  if (cp?.advancesOn?.approval_key !== approvalKey) return;
  stopPlay();
  const nextCp = cps[Math.min(pos.checkpointIndex + 1, cps.length - 1)]!;
  if (nextCp.id === pos.checkpointId) return;
  applyPosition(pos.scenarioId, nextCp.id);
}

export function getScenarioControllerImpl(): ScenarioController {
  return {
    listScenarios: () => ["greenfield", "brownfield", "feature-change", "bug-fix"],
    listCheckpoints: (scenarioId) => SCENARIO_CHECKPOINTS[scenarioId],
    getPosition: () => positionFromState(),
    setPosition(scenarioId, checkpointId) {
      stopPlay();
      applyPosition(scenarioId, checkpointId);
    },
    next() {
      stopPlay();
      const pos = positionFromState();
      const cps = SCENARIO_CHECKPOINTS[pos.scenarioId];
      const nextCp = cps[Math.min(pos.checkpointIndex + 1, cps.length - 1)]!;
      applyPosition(pos.scenarioId, nextCp.id);
      return positionFromState();
    },
    previous() {
      stopPlay();
      const pos = positionFromState();
      const cps = SCENARIO_CHECKPOINTS[pos.scenarioId];
      const prevCp = cps[Math.max(pos.checkpointIndex - 1, 0)]!;
      applyPosition(pos.scenarioId, prevCp.id);
      return positionFromState();
    },
    reset() {
      stopPlay();
      clearWorldCache();
      const pos = positionFromState();
      const cps = SCENARIO_CHECKPOINTS[pos.scenarioId];
      resetFixtureStore();
      applyPosition(pos.scenarioId, cps[0]!.id);
      return positionFromState();
    },
    isPlaying: () => playing,
    setPlaying(p: boolean) {
      if (!p) {
        stopPlay();
        return;
      }
      playing = true;
      stopPlay();
      playing = true;
      playTimer = setInterval(() => {
        const pos = positionFromState();
        if (pos.checkpointIndex >= pos.totalCheckpoints - 1) {
          stopPlay();
          return;
        }
        const cps = SCENARIO_CHECKPOINTS[pos.scenarioId];
        const nextCp = cps[pos.checkpointIndex + 1]!;
        applyPosition(pos.scenarioId, nextCp.id);
      }, 2500 / speed);
    },
    getSpeed: () => speed,
    setSpeed(s: number) {
      speed = s;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
