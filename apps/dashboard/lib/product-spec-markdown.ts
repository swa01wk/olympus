import type { ProductSpecDocument } from "@/src/api/types/product-spec";

export function productSpecToMarkdown(doc: ProductSpecDocument): string {
  const lines: string[] = [`# Product specification`, ``];
  for (const cap of doc.capabilities) {
    lines.push(`## ${cap.name}`, ``);
    if (cap.description) lines.push(cap.description, ``);
    for (const feat of cap.features) {
      lines.push(`### ${feat.name}`, ``);
      if (feat.description) lines.push(feat.description, ``);
      const body = feat.spec.body;
      lines.push(`**Behavior**`, body.behavior, ``);
      if (body.rules?.length) {
        lines.push(`**Rules**`);
        for (const rule of body.rules) {
          lines.push(`- ${rule} ${_provenanceSuffix(feat)}`);
        }
        lines.push(``);
      }
      if (feat.spec.acceptance_criteria.length) {
        lines.push(`**Acceptance criteria**`);
        for (const ac of feat.spec.acceptance_criteria) {
          const gwt = [ac.given && `Given ${ac.given}`, ac.when && `When ${ac.when}`, ac.then && `Then ${ac.then}`]
            .filter(Boolean)
            .join(" · ");
          lines.push(
            `- ${ac.statement}${gwt ? ` (${gwt})` : ""}${ac.mandatory ? " [mandatory]" : ""} ${_provenanceSuffix(feat)}`,
          );
        }
        lines.push(``);
      }
      for (const gap of feat.spec.known_gaps) {
        lines.push(`> Known gap: not confirmed — ${gap.statement}`, ``);
      }
    }
  }
  return lines.join("\n").trim() + "\n";
}

function _provenanceSuffix(feat: ProductSpecDocument["capabilities"][0]["features"][0]): string {
  const prov = feat.spec.provenance;
  if (prov.kind === "greenfield") {
    const ver = prov.product_source_version ?? "?";
    const title = prov.product_source_title ?? "PRD";
    return `[PRD v${ver} · ${title}]`;
  }
  const ev = prov.recovered_evidence[0];
  if (ev) return `[${ev.strength} · ${ev.support_ref}]`;
  return `[${prov.confidence ?? "RECOVERED"}]`;
}
