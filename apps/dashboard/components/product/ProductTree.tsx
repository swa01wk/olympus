import type { Capability, Feature } from "@/lib/contracts/entity-types";

export function ProductTree({
  capabilities,
  features,
  onSelectFeature,
}: {
  capabilities: Capability[];
  features: Feature[];
  onSelectFeature?: (featureId: string) => void;
}) {
  return (
    <ul className="space-y-2 text-sm">
      {capabilities.map((cap) => (
        <li key={cap.id}>
          <span className="font-mono text-amber-300">{cap.key}</span> — {cap.title}
          <ul className="ml-4 mt-1 space-y-1 border-l border-[var(--border)] pl-3">
            {features
              .filter((f) => f.capability_id === cap.id)
              .map((f) => (
                <li key={f.id}>
                  <button
                    type="button"
                    className="text-left hover:text-amber-300"
                    onClick={() => onSelectFeature?.(f.id)}
                  >
                    {f.key} — {f.title}
                  </button>
                </li>
              ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}
