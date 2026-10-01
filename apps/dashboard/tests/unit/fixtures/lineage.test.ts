import { describe, expect, it } from "vitest";
import { buildWorld } from "@/lib/fixtures/engine/build-world";
import { queryLineage } from "@/lib/fixtures/engine/lineage-index";

describe("lineage BFS", () => {
  it("reverse from TicketService method returns nodes", () => {
    const world = buildWorld("feature-change", 11);
    const method = world.codeEntities.find((e) =>
      e.stable_key.includes("TicketService.create_ticket"),
    );
    expect(method).toBeTruthy();
    const graph = queryLineage(world, {
      root_type: "CODE_ENTITY",
      root_id: method!.id,
      direction: "REVERSE",
      depth: 4,
    });
    expect(graph.nodes.length).toBeGreaterThan(0);
  });
});
