import { humanizeReason } from "@/lib/view-models/reason-code";

export function ReasonCode({ code }: { code: string }) {
  return (
    <div className="text-xs">
      <p className="text-[var(--foreground)]">{humanizeReason(code)}</p>
      <p className="font-mono text-[10px] text-[var(--muted)]">{code}</p>
    </div>
  );
}
