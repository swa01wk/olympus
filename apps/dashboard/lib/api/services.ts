import { getDataMode } from "@/lib/config/data-mode";
import type { OlympusServices } from "@/lib/api/olympus-services";

export type { OlympusServices } from "@/lib/api/olympus-services";

let cached: OlympusServices | null = null;

export async function getServices(): Promise<OlympusServices> {
  const mode = getDataMode();
  if (mode === "fixture") {
    const { getFixtureServicesForController } = await import("@/lib/fixtures/store");
    return getFixtureServicesForController();
  }
  if (cached) return cached;
  const { createHttpServices } = await import("@/lib/api/http-services");
  cached = createHttpServices();
  return cached;
}

export async function getScenarioController() {
  if (getDataMode() !== "fixture") return null;
  const { getScenarioControllerImpl } = await import("@/lib/fixtures/controller");
  return getScenarioControllerImpl();
}

/** Invalidate cached live services (fixture path rebuilds per controller position). */
export function invalidateServicesCache() {
  cached = null;
}

/** Client-only hook helper */
export function useServicesSync(): OlympusServices | null {
  return cached;
}
