"use client";

import { Sha } from "@/components/primitives";

export function ShaScopeBanner({
  provisional,
  canonical,
  released,
}: {
  provisional?: string | null;
  canonical?: string | null;
  released?: string | null;
}) {
  return (
    <div className="ol-snap" role="note">
      <span className="ol-label">SHA scope</span>
      <span>
        <strong>Provisional candidate</strong>{" "}
        {provisional ? <Sha value={provisional} /> : "—"}
      </span>
      <span>
        <strong>Canonical assurance</strong> {canonical ? <Sha value={canonical} /> : "—"}
      </span>
      <span>
        <strong>Released baseline</strong> {released ? <Sha value={released} /> : "—"}
      </span>
    </div>
  );
}
