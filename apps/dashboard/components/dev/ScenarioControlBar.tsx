"use client";

import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type {
  ScenarioCheckpointMeta,
  ScenarioId,
  ScenarioPosition,
} from "@/lib/api/scenario-controller";
import { getScenarioController } from "@/lib/api/services";
import { getDataMode } from "@/lib/config/data-mode";
import {
  DEFAULT_CHECKPOINT_ID,
  DEFAULT_SCENARIO,
  formatFxParam,
  FX_SESSION_KEY,
  parseFxParam,
} from "@/lib/api/fx-param";
import { CheckpointGuide } from "./CheckpointGuide";

const SCENARIO_LABELS: Record<ScenarioId, string> = {
  greenfield: "Greenfield",
  brownfield: "Brownfield",
  "feature-change": "Feature Change",
  "bug-fix": "Bug Fix",
};

export function ScenarioControlBar() {
  const mode = getDataMode();
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pos, setPos] = useState<ScenarioPosition | null>(null);
  const [checkpointOptions, setCheckpointOptions] = useState<ScenarioCheckpointMeta[]>([]);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  const fxFromUrl = searchParams.get("fx");
  const fetchingCount = useIsFetching();
  const queryState = fetchingCount > 0 ? "fetching" : "idle";

  const syncUrl = useCallback(
    (scenarioId: ScenarioId, checkpointId: string) => {
      const next = new URLSearchParams(searchParams.toString());
      const fx = formatFxParam(scenarioId, checkpointId);
      next.set("fx", fx);
      if (typeof window !== "undefined") {
        sessionStorage.setItem(FX_SESSION_KEY, fx);
      }
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    if (mode !== "fixture") return;
    let unsub: (() => void) | undefined;
    let cancelled = false;

    void (async () => {
      const controller = await getScenarioController();
      if (!controller || cancelled) return;

      const parsed =
        parseFxParam(fxFromUrl) ??
        parseFxParam(
          typeof window !== "undefined" ? sessionStorage.getItem(FX_SESSION_KEY) : null,
        );
      if (parsed) {
        controller.setPosition(parsed.scenarioId, parsed.checkpointId);
      } else {
        controller.setPosition(DEFAULT_SCENARIO, DEFAULT_CHECKPOINT_ID);
        syncUrl(DEFAULT_SCENARIO, DEFAULT_CHECKPOINT_ID);
      }

      setCheckpointOptions(controller.listCheckpoints(controller.getPosition().scenarioId));
      setPos(controller.getPosition());
      setPlaying(controller.isPlaying());
      setSpeed(controller.getSpeed());

      unsub = controller.subscribe(() => {
        const p = controller.getPosition();
        setPos(p);
        setCheckpointOptions(controller.listCheckpoints(p.scenarioId));
        setPlaying(controller.isPlaying());
        syncUrl(p.scenarioId, p.checkpointId);
        void qc.invalidateQueries();
      });
    })();

    return () => {
      cancelled = true;
      unsub?.();
    };
  }, [mode, fxFromUrl, qc, syncUrl]);

  if (mode !== "fixture" || !pos) return null;

  const run = async (fn: (c: NonNullable<Awaited<ReturnType<typeof getScenarioController>>>) => void) => {
    const controller = await getScenarioController();
    if (!controller) return;
    fn(controller);
  };

  return (
    <div
      className="border-b border-amber-500/30 bg-[var(--surface)] px-4 py-2 text-xs"
      data-testid="scenario-control-bar"
      data-scenario={pos.scenarioId}
      data-checkpoint-id={pos.checkpointId}
      data-checkpoint-index={String(pos.checkpointIndex)}
      data-runtime={pos.runtime}
      data-query-state={queryState}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold uppercase tracking-wide text-amber-400">Fixture playback</span>
        <select
          aria-label="Scenario"
          className="rounded border border-[var(--border)] bg-[var(--raised)] px-2 py-1"
          value={pos.scenarioId}
          onChange={(e) => {
            void run((c) => {
              const scenarioId = e.target.value as ScenarioId;
              const first = c.listCheckpoints(scenarioId)[0]!;
              c.setPosition(scenarioId, first.id);
            });
          }}
        >
          {(Object.keys(SCENARIO_LABELS) as ScenarioId[]).map((id) => (
            <option key={id} value={id}>
              {SCENARIO_LABELS[id]} · Runtime {id === "greenfield" ? "A" : "B"}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="rounded border border-[var(--border)] px-2 py-1 hover:bg-white/5"
          onClick={() => void run((c) => c.previous())}
        >
          ◀ Previous
        </button>
        <button
          type="button"
          className="rounded border border-[var(--border)] px-2 py-1 hover:bg-white/5"
          onClick={() => void run((c) => c.next())}
        >
          ▶ Next
        </button>
        <button
          type="button"
          className="rounded border border-[var(--border)] px-2 py-1 hover:bg-white/5"
          onClick={() => void run((c) => c.reset())}
        >
          ⟲ Reset
        </button>
        <label className="flex items-center gap-1">
          Jump
          <select
            aria-label="Checkpoint"
            className="max-w-[14rem] rounded border border-[var(--border)] bg-[var(--raised)] px-2 py-1"
            value={pos.checkpointId}
            onChange={(e) => {
              void run((c) => c.setPosition(pos.scenarioId, e.target.value));
            }}
          >
            {checkpointOptions.map((cp) => (
              <option key={cp.id} value={cp.id}>
                {cp.id} — {cp.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="rounded border border-[var(--border)] px-2 py-1 hover:bg-white/5"
          onClick={() =>
            void run((c) => {
              const next = !c.isPlaying();
              c.setPlaying(next);
              setPlaying(next);
            })
          }
        >
          {playing ? "❚❚ Pause" : "▶ Play"}
        </button>
        <label className="flex items-center gap-1">
          Speed
          <select
            aria-label="Playback speed"
            className="rounded border border-[var(--border)] bg-[var(--raised)] px-1"
            value={speed}
            onChange={(e) => {
              const s = Number(e.target.value);
              setSpeed(s);
              void run((c) => c.setSpeed(s));
            }}
          >
            {[1, 2, 4].map((s) => (
              <option key={s} value={s}>
                {s}x
              </option>
            ))}
          </select>
        </label>
        <span className="text-[var(--muted)]">
          Checkpoint {pos.checkpointIndex + 1}/{pos.totalCheckpoints} — {pos.meta.label}
        </span>
      </div>
      <CheckpointGuide meta={pos.meta} />
    </div>
  );
}
