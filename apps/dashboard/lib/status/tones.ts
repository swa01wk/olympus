import type { LucideIcon } from "lucide-react";
import {
  CheckCircle2,
  Circle,
  CircleDashed,
  Hexagon,
  Hourglass,
  Loader2,
  OctagonAlert,
  TriangleAlert,
  XCircle,
} from "lucide-react";

export type Tone =
  | "complete"
  | "running"
  | "waiting"
  | "blocked"
  | "failed"
  | "ready"
  | "not_started"
  | "unknown";

export interface ToneSpec {
  label: string;
  tone: Tone;
  icon: LucideIcon;
  className: string;
  shape: "solid" | "ring" | "dashed" | "octagon" | "triangle";
}

const toneMap: Record<Tone, Omit<ToneSpec, "label">> = {
  complete: {
    tone: "complete",
    icon: CheckCircle2,
    className: "text-emerald-400 border-emerald-500/40 bg-emerald-500/10",
    shape: "solid",
  },
  running: {
    tone: "running",
    icon: Loader2,
    className: "text-sky-400 border-sky-500/40 bg-sky-500/10 animate-pulse",
    shape: "solid",
  },
  waiting: {
    tone: "waiting",
    icon: Hourglass,
    className: "text-violet-400 border-violet-500/40 bg-violet-500/10",
    shape: "solid",
  },
  blocked: {
    tone: "blocked",
    icon: OctagonAlert,
    className: "text-orange-400 border-orange-500/40 bg-orange-500/10",
    shape: "octagon",
  },
  failed: {
    tone: "failed",
    icon: XCircle,
    className: "text-rose-400 border-rose-500/40 bg-rose-500/10",
    shape: "solid",
  },
  ready: {
    tone: "ready",
    icon: Circle,
    className: "text-slate-400 border-slate-500/50 bg-transparent",
    shape: "ring",
  },
  not_started: {
    tone: "not_started",
    icon: CircleDashed,
    className: "text-slate-600 border-slate-600 border-dashed bg-transparent",
    shape: "dashed",
  },
  unknown: {
    tone: "unknown",
    icon: TriangleAlert,
    className: "text-zinc-400 border-zinc-500/40 bg-zinc-500/10",
    shape: "triangle",
  },
};

export function toneForExecutionStatus(status: string): ToneSpec {
  const map: Record<string, Tone> = {
    COMPLETED: "complete",
    COMMITTED: "complete",
    STARTED: "running",
    OUTPUT_PRODUCED: "running",
    VALIDATING: "running",
    EXECUTING: "running",
    LEASED: "running",
    QUEUED: "waiting",
    CHECKPOINTED: "waiting",
    BLOCKED: "blocked",
    FAILED: "failed",
    TIMED_OUT: "failed",
    CANCELLED: "failed",
    STALE: "failed",
  };
  const tone = map[status] ?? "unknown";
  return { label: status, ...toneMap[tone] };
}

export function toneForTaskStatus(status: string): ToneSpec {
  const map: Record<string, Tone> = {
    COMPLETED: "complete",
    RUNNING: "running",
    QUEUED: "waiting",
    READY: "ready",
    BLOCKED: "blocked",
    FAILED: "failed",
    DRAFT: "not_started",
    CANCELLED: "failed",
    STALE: "failed",
    REVALIDATION_REQUIRED: "waiting",
  };
  const tone = map[status] ?? "unknown";
  return { label: status, ...toneMap[tone] };
}

export function toneForGeneric(value: string, preferred?: Tone): ToneSpec {
  const tone = preferred ?? "unknown";
  return { label: value, ...toneMap[tone] };
}
