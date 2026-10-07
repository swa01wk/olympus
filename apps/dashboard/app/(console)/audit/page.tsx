import { AuditScreen } from "@/components/screens/AuditScreen";
import { Suspense } from "react";

export default function AuditPage() {
  return (
    <Suspense fallback={<p className="ol-main ol-muted">Loading audit…</p>}>
      <AuditScreen />
    </Suspense>
  );
}
