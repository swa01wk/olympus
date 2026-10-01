import { IDS } from "../ids";
import { SHAS } from "../supportdesk/shas";
import { cloneWorld } from "./world-builder";
import { worldFromLegacyChained } from "./world-from-legacy";
import type { World } from "./world";
import { at, resetClock } from "./clock";
import {
  appendMaterializationClone,
  applyBugFixRemediation,
  applyFeatureChangeIntegrated,
} from "./world-mutations";

export function applyFeatureChangeIndex(index: number): World {
  const { world } = cloneWorld(worldFromLegacyChained());
  resetClock("B", 400 + index * 10);
  world.as_of = at();

  if (index >= 8) {
    applyFeatureChangeIntegrated(world);
  }

  if (index < 5) {
    world.executions = world.executions.filter((e) => e.key !== "EX-551" && e.key !== "EX-552");
    world.executionWorkspaces = world.executionWorkspaces.filter(
      (w) => w.key !== "EX-551" && w.key !== "EX-552",
    );
  }

  world.cycles = world.cycles.filter((c) => c.key !== "DC-004" || index >= 7);
  if (index < 7) {
    world.defect = null;
    world.reproductions = [];
  }

  return world;
}

export function applyBugFixIndex(index: number): World {
  const { world } = cloneWorld(applyFeatureChangeIndex(11));
  resetClock("B", 600 + index * 10);
  world.as_of = at();

  world.repository.canonical_commit =
    index >= 9 ? SHAS.r3Integrated : index >= 6 ? SHAS.ic004Integrated : SHAS.r2Integrated;
  world.cycles.find((c) => c.key === "DC-003")!.state = "COMPLETE";

  if (index >= 9) {
    applyBugFixRemediation(world);
  }
  if (index >= 11) {
    const r3 = world.releases.find((r) => r.key === "R3");
    if (r3) {
      r3.status = "RELEASED";
      r3.integrated_sha = SHAS.r3Integrated;
    }
    world.cycles.find((c) => c.key === "DC-004")!.state = "COMPLETE";
  }
  if (index >= 7 && index < 9) {
    world.cycles.find((c) => c.key === "DC-004")!.state = "ASSURANCE";
  }

  if (index < 7) {
    world.gates = world.gates.filter((g) => g.gate_type !== "BASELINE" || g.status !== "FAIL");
  }

  return world;
}

export function applyBrownfieldVariant(index: number): World {
  const { world } = cloneWorld(worldFromLegacyChained());
  resetClock("B", 100 + index * 10);
  world.as_of = at();

  world.cycles = world.cycles.filter((c) => c.type === "BROWNFIELD_ONBOARDING" || c.key === "DC-001");
  world.tasks = world.tasks.filter((t) => t.delivery_cycle_id === IDS.dc002);
  world.executions = [];
  world.executionWorkspaces = [];
  world.project.readiness_state = index >= 11 ? "READY_FOR_CHANGE" : "ONBOARDING";

  if (index < 11) {
    world.repository.status = index >= 6 ? "READY" : "CLONING";
    world.repositoryWorkspace.state = index >= 6 ? "READY" : "MATERIALIZING";
    appendMaterializationClone(world, index >= 6 ? 1 : index / 6);
  }

  if (index >= 6) {
    world.indexVersions = world.indexVersions.filter((v) => v.kind === "CANONICAL");
  }

  return world;
}

export function applyGreenfieldVariant(index: number): World {
  const { world } = cloneWorld(worldFromLegacyChained());
  resetClock("A", 50 + index * 10);
  world.as_of = at();

  world.repository.source_type = "GREENFIELD_MANAGED";
  world.repository.provider = "LOCAL";
  world.repository.remote_url = index >= 14 ? "https://github.com/acme/supportdesk" : null;
  world.repository.registered_sha = SHAS.gfInit;
  world.repository.canonical_commit = index >= 10 ? SHAS.r1Integrated : index >= 3 ? SHAS.gfInit : null;
  world.repository.released_commit = index >= 14 ? SHAS.r1Integrated : null;

  world.cycles = world.cycles.filter((c) => c.type === "GREENFIELD_BUILD");
  const dc = world.cycles[0];
  if (dc) {
    dc.state =
      index >= 14 ? "COMPLETE" : index >= 12 ? "RELEASE" : index >= 3 ? "DEVELOPMENT" : "PRODUCT_MODEL";
  }

  world.tasks = world.tasks.filter((t) => t.delivery_cycle_id === IDS.dc001);
  world.executions = [];
  world.executionWorkspaces = [];

  return world;
}
