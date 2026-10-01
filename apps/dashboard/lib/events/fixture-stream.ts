import type { DomainEvent } from "@/lib/contracts/entity-types";
import { getFixtureWorld } from "@/lib/fixtures/store";

let timer: ReturnType<typeof setInterval> | null = null;
let lastEmittedSequence = 0;
const deltaListeners = new Set<(events: DomainEvent[]) => void>();

export function subscribeFixtureCheckpointDeltas(listener: (events: DomainEvent[]) => void) {
  deltaListeners.add(listener);
  return () => deltaListeners.delete(listener);
}

/** Called when scenario controller advances checkpoint — emit new domain events once. */
export function notifyFixtureCheckpointAdvanced() {
  const store = getFixtureWorld();
  const delta = store.events.filter((e) => e.sequence > lastEmittedSequence);
  lastEmittedSequence = store.events.length > 0 ? Math.max(...store.events.map((e) => e.sequence)) : 0;
  if (delta.length === 0) return;
  deltaListeners.forEach((l) => l(delta));
}

export function startFixtureStream(
  cycleId: string,
  onEvent: (ev: DomainEvent) => void,
) {
  stopFixtureStream();
  const store = getFixtureWorld();
  const script = store.events.filter((e) => e.delivery_cycle_id === cycleId);
  if (script.length === 0) return;

  subscribeFixtureCheckpointDeltas((events) => {
    events.filter((e) => e.delivery_cycle_id === cycleId).forEach(onEvent);
  });

  let idx = 0;
  timer = setInterval(() => {
    const ev = script[idx % script.length];
    idx += 1;
    onEvent(ev);
  }, 3000);
}

export function stopFixtureStream() {
  if (timer) clearInterval(timer);
  timer = null;
}
