import { IDS } from "../ids";
import { SHAS } from "../supportdesk/shas";
import type { World } from "./world";
import { fid } from "./deterministic-id";
import { at } from "./clock";

const IDX_R2 = fid("idx", "CODEIDX-R2");

/** After IC-003 READY: canonical pointer, index version, IC commits, release R2. */
export function applyFeatureChangeIntegrated(world: World) {
  world.repository.canonical_commit = SHAS.r2Integrated;
  world.repository.released_commit = SHAS.r2Integrated;

  const ic3 = world.ics.find((i) => i.key === "IC-003");
  if (ic3) {
    ic3.integrated_sha = SHAS.r2Integrated;
    ic3.status = "READY";
    ic3.canonical_index_version_id = IDX_R2;
    ic3.ordering = [
      { task_key: "TASK-221", candidate_commit_sha: SHAS.candidate551, position: 0 },
      { task_key: "TASK-222", candidate_commit_sha: SHAS.candidate552, position: 1 },
      { task_key: "TASK-223", candidate_commit_sha: SHAS.candidate553, position: 2 },
      { task_key: "TASK-224", candidate_commit_sha: SHAS.candidate554, position: 3 },
    ];
  }

  if (!world.indexVersions.some((v) => v.id === IDX_R2)) {
    world.indexVersions.push({
      id: IDX_R2,
      repository_id: world.repository.id,
      key: "CODEIDX-R2",
      commit_sha: SHAS.r2Integrated,
      kind: "CANONICAL",
      source: "INTEGRATION",
      scope_ref: "IC-003",
      status: "READY",
    });
  }
  world.indexPointer.canonical_index_version_id = IDX_R2;
  world.indexPointer.released_commit_sha = SHAS.r2Integrated;

  const seq = world.revisions.length + 1;
  if (!world.revisions.some((r) => r.commit_sha === SHAS.r2Integrated)) {
    world.revisions.push({
      id: fid("revision", `ic3-${seq}`),
      repository_id: world.repository.id,
      sequence: seq,
      commit_sha: SHAS.r2Integrated,
      cause: "INTEGRATION_READY",
      integration_candidate_id: IDS.ic003,
      canonical_index_version_id: IDX_R2,
      created_at: at(),
    });
  }

  const r2 = world.releases.find((r) => r.key === "R2");
  if (r2) {
    r2.status = "RELEASED";
    r2.integrated_sha = SHAS.r2Integrated;
    r2.integration_candidate_id = IDS.ic003;
  }
}

export function applyBugFixRemediation(world: World) {
  const ic5Id = fid("ic", "IC-005");
  if (!world.ics.some((i) => i.key === "IC-005")) {
    world.ics.push({
      id: ic5Id,
      key: "IC-005",
      delivery_cycle_id: IDS.dc004,
      repository_id: world.repository.id,
      base_sha: SHAS.ic004Integrated,
      integrated_sha: SHAS.r3Integrated,
      status: "READY",
      supersedes_id: IDS.ic004,
      ordering: [
        {
          task_key: "TASK-303",
          candidate_commit_sha: SHAS.candidate603,
          position: 0,
        },
      ],
    });
  }
  const ic4 = world.ics.find((i) => i.key === "IC-004");
  if (ic4) ic4.status = "SUPERSEDED";

  world.repository.canonical_commit = SHAS.r3Integrated;
  world.repository.released_commit = SHAS.r3Integrated;

  const idxR3 = fid("idx", "CODEIDX-R3");
  if (!world.indexVersions.some((v) => v.id === idxR3)) {
    world.indexVersions.push({
      id: idxR3,
      repository_id: world.repository.id,
      key: "CODEIDX-R3",
      commit_sha: SHAS.r3Integrated,
      kind: "CANONICAL",
      source: "INTEGRATION",
      scope_ref: "IC-005",
      status: "READY",
    });
  }
  world.indexPointer.canonical_index_version_id = idxR3;
  world.indexPointer.released_commit_sha = SHAS.r3Integrated;
}

export function appendMaterializationClone(world: World, progress: number) {
  if (world.materializations.length === 0) {
    world.materializations.push({
      id: fid("mat", "clone-1"),
      repository_id: world.repository.id,
      kind: "CLONE",
      attempt: 1,
      status: progress >= 1 ? "SUCCEEDED" : "RUNNING",
      action_request_ids: [],
      resulting_sha: progress >= 1 ? SHAS.r1Integrated : null,
      observed_default_branch: "main",
      started_at: at(),
      finished_at: progress >= 1 ? at() : null,
      steps: [
        {
          step_key: "fetch_objects",
          label: "Fetch objects",
          status: progress >= 0.5 ? "SUCCEEDED" : "RUNNING",
        },
        {
          step_key: "checkout",
          label: "Checkout main",
          status: progress >= 1 ? "SUCCEEDED" : "PENDING",
        },
      ],
      progress: {
        objects_received: Math.floor(progress * 1200),
        objects_total: 1200,
        bytes_received: Math.floor(progress * 48_000_000),
      },
    });
  }
}
