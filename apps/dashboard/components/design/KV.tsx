export function KV({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex gap-2 text-xs">
      <dt className="shrink-0 text-[var(--muted)]">{label}</dt>
      <dd className={mono ? "truncate font-mono" : "truncate"}>{value}</dd>
    </div>
  );
}

export function KeyChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 font-mono text-xs text-amber-300">
      {children}
    </span>
  );
}

export function ShaChip({ sha }: { sha: string }) {
  const short = sha.length > 12 ? `${sha.slice(0, 7)}…${sha.slice(-4)}` : sha;
  return (
    <span className="font-mono text-xs text-sky-300" title={sha}>
      {short}
    </span>
  );
}
