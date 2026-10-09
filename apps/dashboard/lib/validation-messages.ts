import { isApiError } from "@/src/api/client";

function fromDetail(detail: unknown): string[] {
  if (typeof detail === "string") return detail ? [detail] : [];
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      if (d && typeof d === "object" && "msg" in d) {
        const loc = Array.isArray((d as { loc?: unknown }).loc)
          ? (d as { loc: unknown[] }).loc.join(".")
          : "";
        const msg = String((d as { msg: unknown }).msg);
        return loc ? `${loc}: ${msg}` : msg;
      }
      return typeof d === "string" ? d : JSON.stringify(d);
    });
  }
  if (detail && typeof detail === "object") {
    const o = detail as { errors?: unknown; violations?: unknown };
    return [o.errors, o.violations].flatMap((list) => (Array.isArray(list) ? list.map(String) : []));
  }
  return [];
}

/** Messages from a 422 `{errors}` / `{violations}` body, FastAPI request errors, or a plain failure. */
export function validationMessages(err: unknown): string[] {
  if (isApiError(err)) {
    const messages = fromDetail(err.details);
    return messages.length > 0 ? messages : [err.message];
  }
  if (err instanceof SyntaxError) return [`Invalid JSON: ${err.message}`];
  return [err instanceof Error ? err.message : "Save failed"];
}
