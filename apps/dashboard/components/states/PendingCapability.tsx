export function PendingCapability({
  capabilityId,
  backendPhase,
}: {
  capabilityId: string;
  backendPhase: string;
}) {
  return (
    <div className="rounded border border-dashed border-[var(--border)] p-4 text-sm text-[var(--muted)]">
      Backend capability pending — <span className="font-mono">{capabilityId}</span> (Phase {backendPhase})
    </div>
  );
}
