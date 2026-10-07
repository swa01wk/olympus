import type { ReactNode } from "react";

export type KVRow = [label: string, value: ReactNode];

export function KV({ rows }: { rows: KVRow[] }) {
  return (
    <dl className="ol-kv">
      {rows.map(([k, v], i) => (
        <div key={i} className="ol-kv-r">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}
