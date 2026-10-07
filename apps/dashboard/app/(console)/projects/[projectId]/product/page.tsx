import { ProductSpecsScreen } from "@/components/screens/ProductSpecsScreen";
import { Suspense } from "react";

export default async function ProductPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return (
    <Suspense fallback={<p className="ol-main ol-muted">Loading…</p>}>
      <ProductSpecsScreen projectId={projectId} />
    </Suspense>
  );
}
