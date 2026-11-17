"use client";

import { isApiError } from "@/src/api/client";
import { fetchReview, submitReview } from "@/src/api/autopilot";
import type { ReviewItem } from "@/src/api/types/autopilot";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

type Choice = "keep" | "drop";

function itemKey(item: ReviewItem): string {
  return `${item.subject_type}:${item.subject_id}`;
}

/** Onboarding review: confirm (or correct) what Olympus learned about an existing app. */
export function ReviewLearnedCard({ cycleId }: { cycleId: string }) {
  const qc = useQueryClient();
  const review = useQuery({
    queryKey: ["autopilot", cycleId, "review"],
    queryFn: () => fetchReview(cycleId),
  });
  const [overrides, setOverrides] = useState<Record<string, Choice>>({});
  const submit = useMutation({
    mutationFn: (items: ReviewItem[]) =>
      submitReview(
        cycleId,
        items.map((item) => ({
          subject_type: item.subject_type,
          subject_id: item.subject_id,
          choice: overrides[itemKey(item)] ?? item.suggestion,
        })),
      ),
    onSuccess: () => {
      setOverrides({});
      void qc.invalidateQueries({ queryKey: ["autopilot", cycleId] });
      void qc.invalidateQueries({ queryKey: ["home"] });
    },
  });

  const items = useMemo(() => review.data ?? [], [review.data]);
  const groups = useMemo(() => {
    const out = new Map<string, ReviewItem[]>();
    for (const item of items) out.set(item.group, [...(out.get(item.group) ?? []), item]);
    return [...out.entries()];
  }, [items]);

  if (review.isLoading) return null;
  if (items.length === 0) return null;

  const changed = Object.keys(overrides).length;
  return (
    <article className="sp-card sp-needs" aria-label="Confirm what Olympus learned">
      <h3 className="sp-needs-title">Is this what your app does?</h3>
      <p className="sp-small sp-muted" style={{ marginTop: 0 }}>
        Olympus read your code and ran your tests. Check what it found. Its suggestion is already
        selected; change anything that is wrong.
      </p>
      <div className="sp-subject">
        {groups.map(([group, rows]) => (
          <section key={group}>
            <h4>{group}</h4>
            <ul style={{ listStyle: "none", padding: 0 }}>
              {rows.map((item) => {
                const key = itemKey(item);
                const value = overrides[key] ?? item.suggestion;
                return (
                  <li key={key} className="sp-review-row">
                    <div>
                      <div>{item.title}</div>
                      {item.detail && <div className="sp-small sp-muted">{item.detail}</div>}
                      {item.why && <div className="sp-small sp-muted">{item.why}</div>}
                    </div>
                    <div className="sp-segment" role="radiogroup" aria-label={item.title}>
                      {(["keep", "drop"] as const).map((choice) => (
                        <button
                          key={choice}
                          type="button"
                          role="radio"
                          aria-checked={value === choice}
                          className="sp-segment-btn"
                          onClick={() =>
                            setOverrides((prev) => {
                              const next = { ...prev };
                              if (choice === item.suggestion) delete next[key];
                              else next[key] = choice;
                              return next;
                            })
                          }
                        >
                          {choice === "keep" ? item.keep_label : item.drop_label}
                        </button>
                      ))}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
      {submit.error && (
        <p className="sp-error" role="alert" style={{ marginBottom: 12 }}>
          {isApiError(submit.error) ? submit.error.message : String(submit.error)}
        </p>
      )}
      <div className="sp-row">
        <button
          type="button"
          className="sp-btn sp-btn-primary"
          disabled={submit.isPending}
          onClick={() => submit.mutate(items)}
        >
          {changed > 0 ? `Confirm (${changed} changed)` : "Looks right, confirm"}
        </button>
        <span className="sp-small sp-muted">{items.length} items</span>
      </div>
    </article>
  );
}
