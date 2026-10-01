export type ScenarioId = "greenfield" | "brownfield" | "feature-change" | "bug-fix";

export interface ScenarioCheckpointMeta {
  id: string;
  index: number;
  label: string;
  narrative: string;
  lookAt: string[];
}

export interface ScenarioPosition {
  scenarioId: ScenarioId;
  checkpointId: string;
  checkpointIndex: number;
  totalCheckpoints: number;
  runtime: "A" | "B";
  meta: ScenarioCheckpointMeta;
}

export interface ScenarioController {
  listScenarios(): ScenarioId[];
  listCheckpoints(scenarioId: ScenarioId): ScenarioCheckpointMeta[];
  getPosition(): ScenarioPosition;
  setPosition(scenarioId: ScenarioId, checkpointId: string): void;
  next(): ScenarioPosition;
  previous(): ScenarioPosition;
  reset(): ScenarioPosition;
  isPlaying(): boolean;
  setPlaying(playing: boolean): void;
  getSpeed(): number;
  setSpeed(speed: number): void;
  subscribe(listener: () => void): () => void;
}
