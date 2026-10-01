"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { Panel } from "@/components/design/Panel";
import { ProductTree } from "@/components/product/ProductTree";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { getServices } from "@/lib/api/services";
export default function ProductPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const search = useSearchParams();
  const tab = search.get("tab") ?? "tree";
  const specId = search.get("spec");

  const capsQ = useQuery({
    queryKey: ["capabilities", projectId],
    queryFn: async () => (await getServices()).product.capabilities(projectId),
  });
  const featuresQ = useQuery({
    queryKey: ["features", projectId],
    queryFn: async () => (await getServices()).product.features(projectId),
  });
  const specsQ = useQuery({
    queryKey: ["featureSpecs", projectId],
    queryFn: async () => (await getServices()).product.featureSpecs(projectId),
  });

  const selectedSpec = specsQ.data?.find((s) => s.id === specId) ?? specsQ.data?.[0];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Product & Specs</h1>
      <nav className="flex gap-2 text-xs">
        {(["tree", "specs", "architecture", "deltas"] as const).map((t) => (
          <a
            key={t}
            href={`/projects/${projectId}/product?tab=${t}`}
            className={`rounded border px-2 py-1 ${tab === t ? "border-amber-500" : "border-[var(--border)]"}`}
          >
            {t}
          </a>
        ))}
      </nav>
      {tab === "tree" && capsQ.data && featuresQ.data && (
        <Panel title="Product tree" stateRail="neutral" actions={<FixtureBadge />}>
          <ProductTree capabilities={capsQ.data} features={featuresQ.data} />
        </Panel>
      )}
      {tab === "specs" && selectedSpec && (
        <Panel title="Feature spec" stateRail="neutral" actions={<FixtureBadge />}>
          <p className="font-mono text-amber-300">{selectedSpec.key}</p>
          <p className="text-sm">{selectedSpec.title}</p>
          <p className="text-xs text-[var(--muted)]">status {selectedSpec.status}</p>
        </Panel>
      )}
      {(tab === "architecture" || tab === "deltas") && (
        <Panel title={tab} stateRail="neutral" actions={<FixtureBadge />}>
          <p className="text-xs text-[var(--muted)]">Fixture planning/product modules supply architecture and deltas.</p>
        </Panel>
      )}
    </div>
  );
}
