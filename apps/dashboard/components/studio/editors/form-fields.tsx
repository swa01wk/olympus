"use client";

import { Button } from "@/components/primitives";
import { useState } from "react";

type Row = Record<string, unknown>;

export type FieldSpec = {
  key: string;
  label: string;
  kind?: "text" | "textarea" | "select" | "csv";
  options?: readonly string[];
};

export function asText(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

export function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(asText) : [];
}

export function asRows(value: unknown): Row[] {
  return Array.isArray(value)
    ? value.map((v) => (v && typeof v === "object" && !Array.isArray(v) ? (v as Row) : {}))
    : [];
}

export function TextField({
  label,
  value,
  onChange,
  multiline = false,
  ariaLabel,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  multiline?: boolean;
  ariaLabel?: string;
}) {
  return (
    <label className="ol-field">
      <span className="ol-label">{label}</span>
      {multiline ? (
        <textarea
          rows={3}
          aria-label={ariaLabel}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input aria-label={ariaLabel} value={value} onChange={(e) => onChange(e.target.value)} />
      )}
    </label>
  );
}

function CsvInput({
  value,
  onChange,
  ariaLabel,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  ariaLabel: string;
}) {
  const [text, setText] = useState(() => value.join(", "));
  return (
    <input
      aria-label={ariaLabel}
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        onChange(
          e.target.value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        );
      }}
    />
  );
}

export function StringListField({
  legend,
  itemLabel,
  items,
  onChange,
}: {
  legend: string;
  itemLabel: string;
  items: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <fieldset>
      <legend className="ol-label">{legend}</legend>
      {items.map((item, i) => (
        <div key={i} className="ol-ws-form-line ol-field">
          <input
            aria-label={`${itemLabel} ${i + 1}`}
            value={item}
            onChange={(e) => onChange(items.map((v, j) => (j === i ? e.target.value : v)))}
          />
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Remove ${itemLabel} ${i + 1}`}
            onClick={() => onChange(items.filter((_, j) => j !== i))}
          >
            Remove
          </Button>
        </div>
      ))}
      <div>
        <Button size="sm" onClick={() => onChange([...items, ""])}>
          Add {itemLabel}
        </Button>
      </div>
    </fieldset>
  );
}

function emptyRow(fields: FieldSpec[]): Row {
  const row: Row = {};
  for (const f of fields) {
    row[f.key] = f.kind === "csv" ? [] : f.kind === "select" ? (f.options?.[0] ?? "") : "";
  }
  return row;
}

export function ObjectListField({
  legend,
  itemLabel,
  items,
  fields,
  onChange,
}: {
  legend: string;
  itemLabel: string;
  items: Row[];
  fields: FieldSpec[];
  onChange: (next: Row[]) => void;
}) {
  const update = (i: number, key: string, value: unknown) =>
    onChange(items.map((row, j) => (j === i ? { ...row, [key]: value } : row)));
  return (
    <fieldset>
      <legend className="ol-label">{legend}</legend>
      {items.map((row, i) => (
        <div key={`${items.length}-${i}`} className="ol-ws-form-item">
          {fields.map((f) => {
            const aria = `${itemLabel} ${i + 1} ${f.label}`;
            return (
              <label key={f.key} className="ol-field">
                <span className="ol-label">{f.label}</span>
                {f.kind === "select" ? (
                  <select
                    aria-label={aria}
                    value={asText(row[f.key])}
                    onChange={(e) => update(i, f.key, e.target.value)}
                  >
                    {(f.options ?? []).map((o) => (
                      <option key={o} value={o}>
                        {o}
                      </option>
                    ))}
                  </select>
                ) : f.kind === "csv" ? (
                  <CsvInput
                    ariaLabel={aria}
                    value={asStringList(row[f.key])}
                    onChange={(v) => update(i, f.key, v)}
                  />
                ) : f.kind === "textarea" ? (
                  <textarea
                    rows={2}
                    aria-label={aria}
                    value={asText(row[f.key])}
                    onChange={(e) => update(i, f.key, e.target.value)}
                  />
                ) : (
                  <input
                    aria-label={aria}
                    value={asText(row[f.key])}
                    onChange={(e) => update(i, f.key, e.target.value)}
                  />
                )}
              </label>
            );
          })}
          <div>
            <Button
              size="sm"
              variant="ghost"
              aria-label={`Remove ${itemLabel} ${i + 1}`}
              onClick={() => onChange(items.filter((_, j) => j !== i))}
            >
              Remove
            </Button>
          </div>
        </div>
      ))}
      <div>
        <Button size="sm" onClick={() => onChange([...items, emptyRow(fields)])}>
          Add {itemLabel}
        </Button>
      </div>
    </fieldset>
  );
}
