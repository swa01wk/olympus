import { cn } from "@/lib/utils";
import { toneForExecutionStatus, toneForGeneric, toneForTaskStatus } from "@/lib/status/tones";

type Kind = "task" | "execution" | "generic";

export function StatusBadge({
  value,
  kind = "generic",
  preferred,
  className,
}: {
  value: string;
  kind?: Kind;
  preferred?: Parameters<typeof toneForGeneric>[1];
  className?: string;
}) {
  const spec =
    kind === "task"
      ? toneForTaskStatus(value)
      : kind === "execution"
        ? toneForExecutionStatus(value)
        : toneForGeneric(value, preferred);
  const Icon = spec.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium tabular-nums",
        spec.className,
        className,
      )}
      title={value}
    >
      <Icon className={cn("h-3.5 w-3.5", spec.tone === "running" && "animate-spin")} aria-hidden />
      <span>{spec.label}</span>
    </span>
  );
}
