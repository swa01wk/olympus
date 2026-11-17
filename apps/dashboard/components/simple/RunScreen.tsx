"use client";

import { AutopilotPill } from "@/components/simple/AutopilotPill";
import { NeedsYou } from "@/components/simple/NeedsYou";
import { ReviewLearnedCard } from "@/components/simple/ReviewLearnedCard";
import { RunChat } from "@/components/simple/RunChat";
import { SimpleShell } from "@/components/simple/SimpleShell";
import { StageTimeline } from "@/components/simple/StageTimeline";
import { journeyName } from "@/lib/journey-progress";
import { isApiError } from "@/src/api/client";
import {
  useAutopilot,
  useAutopilotActivity,
  useRetryAutopilot,
  useToggleAutopilot,
} from "@/src/api/hooks/use-autopilot";
import { useDeliveryCycle, useInbox, useProject } from "@/src/api/hooks/use-olympus-queries";
import { queryKeys } from "@/src/api/query-keys";
import { useCycleEventStream } from "@/src/api/sse/use-cycle-event-stream";
import type { ActivityEvent, AutopilotView } from "@/src/api/types/autopilot";
import type { DeliveryCycle } from "@/src/api/types/core";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useCallback, useRef } from "react";

export function RunScreen({ cycleId }: { cycleId: string }) {
  const qc = useQueryClient();
  const cycle = useDeliveryCycle(cycleId);
  const projectId = cycle.data?.project_id;
  const project = useProject(projectId);
  const autopilot = useAutopilot(cycleId);
  const inbox = useInbox({ cycleId });
  const activity = useAutopilotActivity(cycleId);
  const turnHandler = useRef<((payload: Record<string, unknown>) => void) | null>(null);

  const refresh = useCallback(() => {
    void qc.invalidateQueries({ queryKey: queryKeys.cycles.detail(cycleId) });
    void qc.invalidateQueries({ queryKey: ["autopilot", cycleId] });
    void qc.invalidateQueries({ queryKey: ["views", "inbox"] });
  }, [qc, cycleId]);

  useCycleEventStream(cycleId, {
    invalidate: refresh,
    onEvent: (event) => {
      if (event.event_type === "orchestrator.turn_completed") {
        turnHandler.current?.(event.payload);
      }
    },
  });

  const registerTurnHandler = useCallback(
    (handler: (payload: Record<string, unknown>) => void) => {
      turnHandler.current = handler;
    },
    [],
  );

  if (cycle.isError) {
    const missing = isApiError(cycle.error) && cycle.error.status === 404;
    return (
      <SimpleShell narrow>
        <h1 className="sp-h1">{missing ? "Run not found" : "Can’t load this run"}</h1>
        <p className="sp-lede">
          <Link href="/">Back to your projects</Link>
        </p>
      </SimpleShell>
    );
  }
  if (!cycle.data || !projectId) {
    return (
      <SimpleShell>
        <p className="sp-muted">Loading…</p>
      </SimpleShell>
    );
  }

  const inspectHref = `/projects/${projectId}/cycles/${cycleId}`;
  const items = (inbox.data ?? []).filter(
    (i) => !i.delivery_cycle_id || i.delivery_cycle_id === cycleId,
  );

  return (
    <SimpleShell>
      <div className="sp-run-head">
        <div>
          <div className="sp-crumb">
            <Link href="/" className="sp-top-link">
              Projects
            </Link>{" "}
            / {journeyName(cycle.data.type)}
          </div>
          <h1 className="sp-h1" style={{ margin: 0 }}>
            {project.data?.name ?? cycle.data.objective}
          </h1>
        </div>
        <Link href={inspectHref} className="sp-btn">
          Inspect
        </Link>
      </div>

      <div className="sp-run">
        <div className="sp-stack">
          {autopilot.data && (
            <StatusCard view={autopilot.data} cycle={cycle.data} inspectHref={inspectHref} />
          )}
          {autopilot.data?.status === "DONE" && (
            <ResultCard cycle={cycle.data} view={autopilot.data} />
          )}
          {autopilot.data?.step === "review_learned" && <ReviewLearnedCard cycleId={cycleId} />}
          <NeedsYou items={items} projectId={projectId} inspectHref={inspectHref} />
          <section className="sp-card">
            <h2 className="sp-h2">Progress</h2>
            <StageTimeline cycleType={cycle.data.type} cycleState={cycle.data.state} />
          </section>
          <section className="sp-card">
            <h2 className="sp-h2">What happened</h2>
            <ActivityFeed events={activity.data ?? []} />
          </section>
        </div>
        <RunChat projectId={projectId} cycleId={cycleId} registerTurnHandler={registerTurnHandler} />
      </div>
    </SimpleShell>
  );
}

export function StatusCard({
  view,
  cycle,
  inspectHref,
}: {
  view: AutopilotView;
  cycle: DeliveryCycle;
  inspectHref: string;
}) {
  const retry = useRetryAutopilot(cycle.id);
  const turnOn = useToggleAutopilot(cycle.id, true);
  const turnOff = useToggleAutopilot(cycle.id, false);
  const busy = retry.isPending || turnOn.isPending || turnOff.isPending;
  const error = retry.error ?? turnOn.error ?? turnOff.error;
  const total = view.detail.total ?? 0;
  const done = view.detail.done ?? 0;

  let message = view.message;
  let sub: string | null = null;
  if (view.status === "OFF") {
    message = view.supported
      ? "Autopilot is paused. Nothing moves until you turn it back on."
      : "This kind of run isn’t automated yet.";
    sub = view.supported ? null : "Use Inspect to drive it step by step.";
  } else if (view.status === "NEEDS_YOU") {
    sub = "Olympus is waiting for you below.";
  } else if (view.status === "WORKING") {
    sub = "You can leave this page. Olympus keeps going and stops when it needs you.";
  } else if (view.status === "BLOCKED") {
    sub = view.detail.retryable
      ? "Fix the cause if you can (for example, check your API key), then try again."
      : "Open Inspect to see what went wrong.";
  }

  return (
    <section className="sp-card sp-hero" data-status={view.status} aria-live="polite">
      <div style={{ flex: 1, minWidth: 0 }}>
        <AutopilotPill status={view.status} />
        <p className="sp-hero-msg">{message}</p>
        {sub && (
          <p className="sp-small sp-muted" style={{ margin: 0 }}>
            {sub}
          </p>
        )}
        {view.status === "WORKING" && total > 0 && (
          <div
            className="sp-progress"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={done}
          >
            <span style={{ width: `${Math.round((done / total) * 100)}%` }} />
          </div>
        )}
        {error && (
          <p className="sp-error" role="alert" style={{ marginTop: 8 }}>
            {isApiError(error) ? error.message : String(error)}
          </p>
        )}
      </div>
      <div className="sp-row" style={{ flexShrink: 0 }}>
        {view.status === "BLOCKED" && view.detail.retryable && (
          <button
            type="button"
            className="sp-btn sp-btn-primary"
            disabled={busy}
            onClick={() => retry.mutate()}
          >
            Try again
          </button>
        )}
        {view.status === "BLOCKED" && (
          <Link href={inspectHref} className="sp-btn">
            Details
          </Link>
        )}
        {view.status === "OFF" && view.supported && (
          <button
            type="button"
            className="sp-btn sp-btn-primary"
            disabled={busy}
            onClick={() => turnOn.mutate()}
          >
            Turn Autopilot on
          </button>
        )}
        {(view.status === "WORKING" || view.status === "NEEDS_YOU") && (
          <button
            type="button"
            className="sp-btn sp-btn-ghost"
            disabled={busy}
            onClick={() => turnOff.mutate()}
          >
            Pause
          </button>
        )}
      </div>
    </section>
  );
}

function ResultCard({ cycle, view }: { cycle: DeliveryCycle; view: AutopilotView }) {
  if (cycle.type === "BROWNFIELD_ONBOARDING") {
    return (
      <section className="sp-card sp-stack" style={{ gap: 8 }}>
        <h2 className="sp-h2" style={{ margin: 0 }}>
          Olympus knows your app now
        </h2>
        <p className="sp-small" style={{ margin: 0 }}>
          It can add features and fix bugs while protecting the behavior you confirmed. Your
          folder was not changed.
        </p>
      </section>
    );
  }
  if (cycle.state !== "COMPLETE") return null;
  const { branch, folder } = view.detail;
  return (
    <section className="sp-card sp-stack" style={{ gap: 8 }}>
      <h2 className="sp-h2" style={{ margin: 0 }}>
        Your app is released
      </h2>
      {branch && folder ? (
        <>
          <p className="sp-small" style={{ margin: 0 }}>
            The code is in your folder <code className="sp-code">{folder}</code> on its own
            branch. Your files were not touched. To look at it:
          </p>
          <code className="sp-code" style={{ display: "block", padding: "8px 10px" }}>
            git checkout {branch}
          </code>
        </>
      ) : view.code_path ? (
        <p className="sp-small" style={{ margin: 0 }}>
          The code is in <code className="sp-code">{view.code_path}</code>. Clone it with{" "}
          <code className="sp-code">git clone {view.code_path} my-app</code>.
        </p>
      ) : (
        <p className="sp-small sp-muted" style={{ margin: 0 }}>
          The code is in the project repository (see Inspect → Code).
        </p>
      )}
    </section>
  );
}

function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="sp-small sp-muted" style={{ margin: 0 }}>
        Nothing yet.
      </p>
    );
  }
  const newestFirst = [...events].reverse();
  return (
    <ol className="sp-activity">
      {newestFirst.map((e) => (
        <li key={e.id}>
          <time dateTime={e.occurred_at}>{formatTime(e.occurred_at)}</time>
          <span data-status={e.payload.status}>{e.payload.message}</span>
        </li>
      ))}
    </ol>
  );
}

function formatTime(iso: string): string {
  // Backend timestamps are naive UTC.
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

