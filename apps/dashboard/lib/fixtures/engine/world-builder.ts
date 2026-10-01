import type { DomainEvent } from "@/lib/contracts/entity-types";
import { at, currentAsOf, tick } from "./clock";
import type { World } from "./world";
import { fid } from "./deterministic-id";

export class WorldBuilder {
  readonly world: World;

  constructor(world: World) {
    this.world = world;
  }

  setAsOf() {
    this.world.as_of = currentAsOf();
  }

  advanceMinutes(m: number) {
    tick(m);
    this.setAsOf();
  }

  emit(
    partial: Omit<DomainEvent, "id" | "sequence"> & { id?: string },
  ): DomainEvent {
    this.world.eventSeq += 1;
    const ev: DomainEvent = {
      id: partial.id ?? fid("event", `${this.world.eventSeq}:${partial.event_type}`),
      sequence: this.world.eventSeq,
      ...partial,
    };
    this.world.events.push(ev);
    return ev;
  }
}

export function cloneWorld(w: World): { world: World } {
  return { world: structuredClone(w) };
}
