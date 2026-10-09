"use client";

import { Button, Label, Panel } from "@/components/primitives";
import { JsonDiffView } from "@/components/studio/JsonDiffView";
import { diffJsonBodies, type DiffLine } from "@/lib/json-line-diff";
import { validationMessages } from "@/lib/validation-messages";
import { useState, type ReactNode } from "react";

type SavedEdit = { from: number; to: number; diff: DiffLine[] };

function changesWithContext(lines: DiffLine[], context = 2): DiffLine[] {
  const keep = new Set<number>();
  lines.forEach((l, i) => {
    if (l.kind === "same") return;
    for (let j = Math.max(0, i - context); j <= Math.min(lines.length - 1, i + context); j += 1) {
      keep.add(j);
    }
  });
  return lines.filter((_, i) => keep.has(i));
}

const stringify = (value: unknown) => JSON.stringify(value ?? {}, null, 2);

export function SubjectVersionEditor<T>({
  title,
  subjectId,
  initial,
  beforeVersion,
  deliveryCycleId,
  renderForm,
  fromRaw,
  onSave,
}: {
  title: string;
  subjectId: string;
  initial: T;
  beforeVersion: number;
  deliveryCycleId: string;
  renderForm: (value: T, onChange: (next: T) => void) => ReactNode;
  /** Shape-check parsed raw JSON; throw an Error with a readable message on mismatch. */
  fromRaw: (raw: unknown) => T;
  onSave: (
    value: T,
    meta: { note: string; delivery_cycle_id: string },
  ) => Promise<{ id: string; version: number }>;
}) {
  const [mode, setMode] = useState<"form" | "json">("form");
  const [draft, setDraft] = useState<T>(initial);
  const [raw, setRaw] = useState(() => stringify(initial));
  const [formKey, setFormKey] = useState(0);
  const [syncedSubjectId, setSyncedSubjectId] = useState(subjectId);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState<SavedEdit | null>(null);

  if (syncedSubjectId !== subjectId) {
    setSyncedSubjectId(subjectId);
    setDraft(initial);
    setRaw(stringify(initial));
    setFormKey((k) => k + 1);
  }

  const parseRaw = (): T => fromRaw(JSON.parse(raw) as unknown);

  const switchMode = (next: "form" | "json") => {
    if (next === mode) return;
    setErrors([]);
    if (next === "json") {
      setRaw(stringify(draft));
      setMode("json");
      return;
    }
    try {
      setDraft(parseRaw());
      setFormKey((k) => k + 1);
      setMode("form");
    } catch (e) {
      setErrors(validationMessages(e));
    }
  };

  const save = async () => {
    setBusy(true);
    setErrors([]);
    try {
      const value = mode === "json" ? parseRaw() : draft;
      const res = await onSave(value, { note: note.trim(), delivery_cycle_id: deliveryCycleId });
      setSaved({ from: beforeVersion, to: res.version, diff: diffJsonBodies(initial, value) });
      setNote("");
    } catch (e) {
      setErrors(validationMessages(e));
    } finally {
      setBusy(false);
    }
  };

  const changed = saved ? changesWithContext(saved.diff) : [];

  return (
    <Panel
      title={title}
      sub={`Direct edit · v${beforeVersion} → new PROPOSED version + approval`}
      actions={
        <div className="ol-seg" role="group" aria-label="Editor mode">
          <button
            type="button"
            className={`ol-seg-i ${mode === "form" ? "is-on" : ""}`}
            aria-pressed={mode === "form"}
            onClick={() => switchMode("form")}
          >
            Form
          </button>
          <button
            type="button"
            className={`ol-seg-i ${mode === "json" ? "is-on" : ""}`}
            aria-pressed={mode === "json"}
            onClick={() => switchMode("json")}
          >
            Raw JSON
          </button>
        </div>
      }
    >
      <div className="ol-ws-form">
        {mode === "form" ? (
          <div key={formKey} className="ol-ws-form">
            {renderForm(draft, setDraft)}
          </div>
        ) : (
          <label className="ol-field">
            <span className="ol-label">Body (JSON)</span>
            <textarea
              className="ol-ws-pre"
              rows={16}
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
            />
          </label>
        )}
        <label className="ol-field">
          <span className="ol-label">Note</span>
          <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <div>
          <Button variant="primary" disabled={busy} onClick={() => void save()}>
            Save as new version
          </Button>
        </div>
        {errors.length > 0 && (
          <div role="alert">
            <Label>Validation errors</Label>
            <ul className="ol-ws-bullets ol-chat-err">
              {errors.map((msg, i) => (
                <li key={`${i}-${msg}`}>{msg}</li>
              ))}
            </ul>
          </div>
        )}
        {saved && (
          <div role="status">
            <Label>
              Saved v{saved.from} → v{saved.to}
            </Label>
            <p className="ol-body-sm ol-muted">
              A fresh approval for v{saved.to} is pending in the Decision panel.
            </p>
            {changed.length > 0 ? (
              <JsonDiffView lines={changed} label={`Diff v${saved.from} → v${saved.to}`} />
            ) : (
              <p className="ol-body-sm ol-muted">No changes to the body.</p>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
