"use client";

import { IdRef, Label } from "@/components/primitives";

export type WhyView = {
  summary: string;
  checks?: [string, boolean | null, string?][];
  blocking?: string[];
  policy?: string;
  inputs?: string;
  next?: string;
  evaluated?: string;
};

export function WhyPanel({ why, onRef }: { why: WhyView; onRef?: (id: string) => void }) {
  return (
    <div className="ol-why">
      <p className="ol-why-sum">{why.summary}</p>
      {why.checks && (
        <ul className="ol-checks">
          {why.checks.map(([label, ok, detail], i) => (
            <li
              key={i}
              className={
                ok === true ? "ol-check is-ok" : ok === false ? "ol-check is-no" : "ol-check is-na"
              }
            >
              <span className="ol-check-g" aria-hidden="true">
                {ok === true ? "✓" : ok === false ? "✕" : "—"}
              </span>
              <span className="ol-check-l">{label}</span>
              {detail && <span className="ol-check-d">{detail}</span>}
            </li>
          ))}
        </ul>
      )}
      {why.blocking && why.blocking.length > 0 && (
        <div className="ol-why-row">
          <Label>Blocking records</Label>
          <div className="ol-chips">
            {why.blocking.map((b) => (
              <IdRef key={b} id={b} onNavigate={onRef} />
            ))}
          </div>
        </div>
      )}
      <div className="ol-why-meta">
        {why.policy && (
          <span>
            <span className="ol-label">Policy</span> <span className="ol-id">{why.policy}</span>
          </span>
        )}
        {why.inputs && (
          <span>
            <span className="ol-label">Inputs</span> <span className="ol-id">{why.inputs}</span>
          </span>
        )}
        {why.evaluated && (
          <span>
            <span className="ol-label">Evaluated</span> <span className="ol-sha">{why.evaluated}</span>
          </span>
        )}
      </div>
      {why.next && (
        <p className="ol-why-next">
          <span className="ol-label">Next</span> {why.next}
        </p>
      )}
    </div>
  );
}
