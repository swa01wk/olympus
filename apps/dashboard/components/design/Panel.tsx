import { cn } from "@/lib/utils";

export function Panel({
  title,
  stateRail,
  actions,
  children,
  className,
}: {
  title: string;
  stateRail?: "complete" | "running" | "blocked" | "failed" | "waiting" | "neutral";
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const rail: Record<string, string> = {
    complete: "bg-emerald-500",
    running: "bg-sky-400",
    blocked: "bg-orange-500",
    failed: "bg-rose-500",
    waiting: "bg-violet-400",
    neutral: "bg-[var(--border)]",
  };
  return (
    <section
      className={cn(
        "overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
    >
      <header className="flex items-center gap-2 border-b border-[var(--border)] px-3 py-2">
        <div className={cn("h-8 w-0.5 shrink-0 rounded", rail[stateRail ?? "neutral"])} aria-hidden />
        <h2 className="flex-1 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          {title}
        </h2>
        {actions}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}
