"use client";

import { Label } from "@/components/primitives";
import { useExpectedBehaviorReview } from "@/src/api/hooks/use-journey-queries";

type Gwt = { given?: string | null; when?: string | null; then?: string | null };

function GivenWhenThen({ gwt }: { gwt: Gwt }) {
  return (
    <>
      <p className="ol-body-sm">
        <strong>Given</strong> {gwt.given || "—"}
      </p>
      <p className="ol-body-sm">
        <strong>When</strong> {gwt.when || "—"}
      </p>
      <p className="ol-body-sm">
        <strong>Then</strong> {gwt.then || "—"}
      </p>
    </>
  );
}

function AcBlock({
  title,
  lineageKey,
  statement,
  gwt,
}: {
  title: string;
  lineageKey?: string;
  statement: string;
  gwt: Gwt;
}) {
  return (
    <div className="ol-ws-spec-read">
      <p className="ol-label">{title}</p>
      {lineageKey && <p className="ol-id">{lineageKey}</p>}
      <p className="ol-body-sm">{statement}</p>
      <GivenWhenThen gwt={gwt} />
    </div>
  );
}

export function ExpectedBehaviorDecisionPreview({ resolutionId }: { resolutionId: string }) {
  const review = useExpectedBehaviorReview(resolutionId);
  if (review.isLoading) {
    return <p className="ol-body-sm ol-muted">Loading expected behaviour…</p>;
  }
  if (review.isError || !review.data) {
    return <p className="ol-body-sm ol-muted">Could not load expected behaviour review.</p>;
  }
  const data = review.data;
  return (
    <div className="ol-decision-subject">
      <div>
        <Label>Classification</Label>
        <div>{data.classification}</div>
      </div>
      <div>
        <Label>Kira&apos;s statement</Label>
        <p className="ol-body-sm">{data.statement}</p>
      </div>
      {data.proposed_ac ? (
        <AcBlock
          title="Proposed acceptance criterion"
          lineageKey={data.proposed_ac.lineage_key}
          statement={data.proposed_ac.statement || data.statement}
          gwt={data.proposed_ac}
        />
      ) : (
        <p className="ol-body-sm ol-muted">No new acceptance criterion proposed.</p>
      )}
      {data.cited_acceptance_criteria.map((ac) => (
        <AcBlock
          key={ac.lineage_key}
          title="Cited acceptance criterion"
          lineageKey={ac.lineage_key}
          statement={ac.statement}
          gwt={ac}
        />
      ))}
      <div>
        <Label>Questions for the reporter</Label>
        {data.questions.length > 0 ? (
          <ul className="ol-ws-bullets">
            {data.questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        ) : (
          <p className="ol-body-sm ol-muted">No open questions.</p>
        )}
      </div>
      <div>
        <Label>Contradicted baselines</Label>
        {data.contradicted_baselines.length > 0 ? (
          data.contradicted_baselines.map((bl) => (
            <div key={bl.id} className="ol-ws-spec-read">
              <p className="ol-id">
                {bl.lineage_key} · {bl.status}
              </p>
              <GivenWhenThen gwt={bl} />
            </div>
          ))
        ) : (
          <p className="ol-body-sm ol-muted">No baselines contradicted.</p>
        )}
      </div>
    </div>
  );
}
