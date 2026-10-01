export type DataMode = "live" | "fixture";

export function getDataMode(): DataMode {
  const mode = process.env.NEXT_PUBLIC_OLYMPUS_DATA_MODE ?? "fixture";
  return mode === "live" ? "live" : "fixture";
}

export function getFixtureScenario(): string {
  return process.env.NEXT_PUBLIC_FIXTURE_SCENARIO ?? "feature-change:05-development-running";
}
