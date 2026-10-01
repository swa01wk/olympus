import { expect, type Page } from "@playwright/test";
import type { ScenarioId } from "@/lib/api/scenario-controller";
import { formatFxParam } from "@/lib/api/fx-param";
import { CYCLE_IDS, PROJECT_ID } from "../fixtures/journey-expectations";

export class ScenarioHelper {
  constructor(private readonly page: Page) {}

  async gotoCheckpoint(
    scenarioId: ScenarioId,
    checkpointId: string,
    path = "/projects",
  ) {
    const fx = formatFxParam(scenarioId, checkpointId);
    const url = path.includes("?") ? `${path}&fx=${fx}` : `${path}?fx=${fx}`;
    await this.page.goto(url);
    await this.page.evaluate((f) => sessionStorage.setItem("olympus.fx", f), fx);
    await this.waitSettled(scenarioId, checkpointId);
  }

  cycleIdForKey(cycleKey: string): string | undefined {
    const map: Record<string, string> = {
      "DC-001": CYCLE_IDS.dc001,
      "DC-002": CYCLE_IDS.dc002,
      "DC-003": CYCLE_IDS.dc003,
      "DC-004": CYCLE_IDS.dc004,
    };
    return map[cycleKey];
  }

  /** Load checkpoint on project shell; preserves ?fx= across navigations. */
  async gotoProjectCheckpoint(
    scenarioId: ScenarioId,
    checkpointId: string,
    cycleKey?: string,
  ) {
    const fx = formatFxParam(scenarioId, checkpointId);
    const cycleId = cycleKey ? this.cycleIdForKey(cycleKey) : undefined;
    const qs = new URLSearchParams({ fx });
    if (cycleId) qs.set("cycle", cycleId);
    await this.page.goto(`/projects/${PROJECT_ID}?${qs.toString()}`);
    await this.page.evaluate((f) => sessionStorage.setItem("olympus.fx", f), fx);
    await this.waitSettled(scenarioId, checkpointId);
  }

  bar() {
    return this.page.getByTestId("scenario-control-bar");
  }

  async waitSettled(scenarioId: ScenarioId, checkpointId: string) {
    const bar = this.bar();
    await expect(bar).toBeVisible({ timeout: 30_000 });
    await expect(bar).toHaveAttribute("data-checkpoint-id", checkpointId);
    await expect(bar).toHaveAttribute("data-scenario", scenarioId);
    await expect.poll(async () => bar.getAttribute("data-query-state")).toBe("idle");
  }

  async next() {
    await this.bar().getByRole("button", { name: "▶ Next" }).click();
  }

  async previous() {
    await this.bar().getByRole("button", { name: "◀ Previous" }).click();
  }

  async reset() {
    await this.bar().getByRole("button", { name: "⟲ Reset" }).click();
  }

  async jump(checkpointId: string) {
    await this.bar().getByLabel("Checkpoint").selectOption(checkpointId);
  }

  async expectPosition(scenarioId: ScenarioId, checkpointId: string) {
    const bar = this.bar();
    await expect(bar).toHaveAttribute("data-scenario", scenarioId);
    await expect(bar).toHaveAttribute("data-checkpoint-id", checkpointId);
  }

  async expectCheckpointIndex(index: number) {
    await expect(this.bar()).toHaveAttribute("data-checkpoint-index", String(index));
  }
}
