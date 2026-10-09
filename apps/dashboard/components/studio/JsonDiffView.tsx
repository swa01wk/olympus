import type { DiffLine } from "@/lib/json-line-diff";

export function JsonDiffView({ lines, label = "Revision diff" }: { lines: DiffLine[]; label?: string }) {
  return (
    <pre className="ol-ws-pre ol-revision-diff" aria-label={label}>
      {lines.map((line, i) => (
        <div
          key={`${i}-${line.kind}`}
          className={
            line.kind === "add"
              ? "ol-diff-add"
              : line.kind === "remove"
                ? "ol-diff-remove"
                : "ol-diff-same"
          }
        >
          {line.kind === "add" ? "+ " : line.kind === "remove" ? "- " : "  "}
          {line.text}
        </div>
      ))}
    </pre>
  );
}
