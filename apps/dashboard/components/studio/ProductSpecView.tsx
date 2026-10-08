"use client";

import { Button, EmptyState, Panel } from "@/components/primitives";
import { productSpecToMarkdown } from "@/lib/product-spec-markdown";
import { getProductSpec, getSourceContent } from "@/src/api/resources";
import type {
  ProductSpecDocument,
  ProductSpecGreenfieldProvenance,
} from "@/src/api/types/product-spec";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";

function ProvenanceChip({
  projectId,
  provenance,
  featureName,
}: {
  projectId: string;
  provenance: ProductSpecDocument["capabilities"][0]["features"][0]["spec"]["provenance"];
  featureName: string;
}) {
  const [open, setOpen] = useState(false);
  const green = provenance.kind === "greenfield" ? (provenance as ProductSpecGreenfieldProvenance) : null;
  const sourceId = green?.product_source_id ?? undefined;
  const content = useQuery({
    queryKey: ["source-content", projectId, sourceId],
    queryFn: () => getSourceContent(projectId, sourceId!),
    enabled: open && Boolean(sourceId),
  });

  if (provenance.kind === "greenfield") {
    const label = `PRD v${provenance.product_source_version ?? "?"} · Feature: ${featureName}`;
    return (
      <button type="button" className="ol-ws-chip" onClick={() => setOpen((v) => !v)}>
        {label}
        {open && content.data && (
          <pre className="ol-ws-pre ol-body-sm">{content.data.text.slice(0, 1200)}</pre>
        )}
      </button>
    );
  }
  const ev = provenance.recovered_evidence[0];
  const label = ev
    ? `${ev.strength} · ${ev.support_ref}`
    : `${provenance.confidence ?? "RECOVERED"}`;
  return <span className="ol-ws-chip">{label}</span>;
}

export function ProductSpecView({ projectId }: { projectId: string }) {
  const doc = useQuery({
    queryKey: ["product-spec", projectId],
    queryFn: () => getProductSpec(projectId),
  });

  const copyMd = useCallback(async () => {
    if (!doc.data) return;
    await navigator.clipboard.writeText(productSpecToMarkdown(doc.data));
  }, [doc.data]);

  if (doc.isLoading) return <p className="ol-body-sm ol-muted">Loading product spec…</p>;
  if (doc.isError) {
    return <EmptyState title="Product spec unavailable" description="Could not load canonical model." />;
  }
  if (!doc.data?.capabilities.length) {
    return (
      <EmptyState
        title="No canonical specs yet"
        description="Approve scope (greenfield) or promote recovered specs (brownfield)."
      />
    );
  }

  return (
    <Panel
      title="Product spec"
      sub="Canonical model · one document"
      actions={
        <Button variant="quiet" type="button" onClick={() => void copyMd()}>
          Copy as Markdown
        </Button>
      }
      className="ol-product-spec"
    >
      {doc.data.capabilities.map((cap) => (
        <section key={cap.key} className="ol-product-spec-cap">
          <h3 className="ol-section">{cap.name}</h3>
          {cap.description && <p className="ol-body-sm">{cap.description}</p>}
          {cap.features.map((feat) => (
            <article key={feat.id} className="ol-product-spec-feature">
              <h4 className="ol-label">
                {feat.key} · {feat.name}
              </h4>
              <p className="ol-body-sm">
                <ProvenanceChip
                  projectId={projectId}
                  provenance={feat.spec.provenance}
                  featureName={feat.name}
                />
              </p>
              {feat.description && <p className="ol-body-sm">{feat.description}</p>}
              <p className="ol-body-sm">
                <strong>Behavior.</strong> {feat.spec.body.behavior}
              </p>
              {feat.spec.body.rules?.length > 0 && (
                <>
                  <p className="ol-label">Rules</p>
                  <ul className="ol-ws-bullets">
                    {feat.spec.body.rules.map((rule) => (
                      <li key={rule}>
                        {rule}{" "}
                        <ProvenanceChip
                          projectId={projectId}
                          provenance={feat.spec.provenance}
                          featureName={feat.name}
                        />
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {feat.spec.acceptance_criteria.length > 0 && (
                <>
                  <p className="ol-label">Acceptance criteria</p>
                  <ul className="ol-ws-bullets">
                    {feat.spec.acceptance_criteria.map((ac) => (
                      <li key={ac.id}>
                        {ac.given && <span>Given {ac.given}. </span>}
                        {ac.when && <span>When {ac.when}. </span>}
                        {ac.then && <span>Then {ac.then}. </span>}
                        {!ac.given && !ac.when && !ac.then && ac.statement}
                        {ac.mandatory && <span className="ol-muted"> (mandatory)</span>}{" "}
                        <ProvenanceChip
                          projectId={projectId}
                          provenance={feat.spec.provenance}
                          featureName={feat.name}
                        />
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {feat.spec.known_gaps.map((gap) => (
                <p key={gap.id} className="ol-body-sm ol-muted">
                  Known gap: not confirmed — {gap.statement}
                </p>
              ))}
            </article>
          ))}
        </section>
      ))}
    </Panel>
  );
}
