const T0: Record<"A" | "B", number> = {
  A: Date.parse("2025-08-01T10:00:00.000Z"),
  B: Date.parse("2025-09-15T10:00:00.000Z"),
};

let minuteOffset = 0;
let runtime: "A" | "B" = "B";

export function resetClock(rt: "A" | "B", startMinute = 0) {
  runtime = rt;
  minuteOffset = startMinute;
}

export function tick(minutes = 1) {
  minuteOffset += minutes;
}

export function at(minutes?: number): string {
  const m = minutes ?? minuteOffset;
  return new Date(T0[runtime] + m * 60_000).toISOString();
}

export function currentAsOf(): string {
  return at();
}
