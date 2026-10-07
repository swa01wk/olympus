import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchInbox } from "@/src/api/resources";

describe("fetchInbox", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("passes project_id and delivery_cycle_id query params", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => "[]",
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchInbox({ projectId: "proj-1", cycleId: "cycle-2" });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("project_id=proj-1");
    expect(url).toContain("delivery_cycle_id=cycle-2");
  });
});
