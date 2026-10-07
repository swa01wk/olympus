import type { ScreenId } from "@/src/control-plane/lanes";

export function screenHref(
  screen: ScreenId | "INT" | "AUD",
  projectId: string,
  cycleId: string,
): string {
  switch (screen) {
    case "S01":
      return `/projects/${projectId}`;
    case "S02":
      return `/projects/${projectId}/cycles/${cycleId}`;
    case "S03":
      return `/projects/${projectId}/product?cycle=${cycleId}`;
    case "S04":
      return `/projects/${projectId}/cycles/${cycleId}/tasks`;
    case "S05":
      return `/projects/${projectId}/executions?cycle=${cycleId}`;
    case "S06":
      return `/projects/${projectId}/code?cycle=${cycleId}`;
    case "S07":
      return `/projects/${projectId}/lineage?cycle=${cycleId}`;
    case "S08":
      return `/projects/${projectId}/cycles/${cycleId}/impact`;
    case "S09":
      return `/projects/${projectId}/cycles/${cycleId}/assurance`;
    case "S10":
      return `/projects/${projectId}/cycles/${cycleId}/outcome`;
    case "INT":
      return `/projects/${projectId}/integrations`;
    case "AUD":
      return `/audit?project=${projectId}`;
    default:
      return `/projects/${projectId}/cycles/${cycleId}`;
  }
}
