import { cn } from "@/lib/utils";
import { AlertTriangle, CheckSquare, HelpCircle, Stamp } from "lucide-react";

const styles: Record<string, { icon: typeof CheckSquare; className: string; label: string }> = {
  FACT: {
    icon: CheckSquare,
    className: "border-solid border-emerald-500/50 bg-emerald-500/10",
    label: "FACT",
  },
  INFERENCE: {
    icon: HelpCircle,
    className: "border-dashed border-sky-500/50",
    label: "INFERENCE",
  },
  UNCERTAINTY: {
    icon: AlertTriangle,
    className: "border-amber-500/50 bg-amber-500/10",
    label: "UNCERTAINTY",
  },
  DECISION: {
    icon: Stamp,
    className: "border-violet-500/50",
    label: "DECISION",
  },
  ASSUMPTION: {
    icon: HelpCircle,
    className: "border-dotted border-slate-500",
    label: "ASSUMPTION",
  },
};

export function KnowledgeChip({ value }: { value: string }) {
  const spec = styles[value] ?? {
    icon: HelpCircle,
    className: "border-zinc-500",
    label: value,
  };
  const Icon = spec.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium",
        spec.className,
      )}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {spec.label}
    </span>
  );
}
