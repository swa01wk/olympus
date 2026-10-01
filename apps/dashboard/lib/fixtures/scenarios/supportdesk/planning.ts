import type { Architecture, ImplementationSpec, SpecDelta, TaskPlan } from "@/lib/contracts/entity-types";
import { IDS } from "./ids";

export function buildPlanning() {
  const architecture: Architecture[] = [
    {
      id: "11111111-1111-4111-8111-111111112501",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc001,
      key: "ARCH-001",
      version: 1,
      status: "APPROVED",
    },
  ];

  const implementationSpecs: ImplementationSpec[] = [
    {
      id: IDS.ia003,
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc003,
      key: "IA-003",
      version: 1,
      status: "APPROVED",
      title: "Priority column + API surface",
      feature_spec_refs: ["FS-014@v2"],
    },
  ];

  const specDeltas: SpecDelta[] = [
    {
      id: "11111111-1111-4111-8111-111111112502",
      feature_spec_id: IDS.fs014,
      from_version: 1,
      to_version: 2,
      summary: "Add ticket priority field and validation rules",
    },
  ];

  const taskPlans: TaskPlan[] = [
    {
      id: "11111111-1111-4111-8111-111111112503",
      delivery_cycle_id: IDS.dc003,
      version: 1,
      status: "COMPILED",
    },
  ];

  return { architecture, implementationSpecs, specDeltas, taskPlans };
}
