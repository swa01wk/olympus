import type { LensId } from "@/src/control-plane/lanes";

export type CycleMapSearch = {
  selected?: string;
  lens?: LensId;
  view?: "graph" | "list";
};

export function cycleMapPath(projectId: string, cycleId: string, q?: CycleMapSearch): string {
  const params = new URLSearchParams();
  if (q?.selected) params.set("selected", q.selected);
  if (q?.lens && q.lens !== "lifecycle") params.set("lens", q.lens);
  if (q?.view && q.view !== "graph") params.set("view", q.view);
  const s = params.toString();
  return `/projects/${projectId}/cycles/${cycleId}${s ? `?${s}` : ""}`;
}

export function parseCycleMapSearch(sp: URLSearchParams): Required<CycleMapSearch> | CycleMapSearch {
  const lens = sp.get("lens");
  const view = sp.get("view");
  return {
    selected: sp.get("selected") ?? undefined,
    lens: (lens as LensId) || "lifecycle",
    view: view === "list" ? "list" : "graph",
  };
}
