"use client";

import { SimpleShell } from "@/components/simple/SimpleShell";
import { newIdempotencyKey } from "@/lib/utils";
import { isApiError } from "@/src/api/client";
import { useStartJourney } from "@/src/api/hooks/use-autopilot";
import { useRouter } from "next/navigation";
import { useRef, useState, type DragEvent } from "react";

const TEXT_TYPES = [".md", ".markdown", ".txt"];
const MIN_PRD_CHARS = 40;

function nameFromPrd(text: string): string {
  const heading = text.split("\n").find((l) => /^#\s+\S/.test(l));
  if (!heading) return "";
  return heading
    .replace(/^#\s+/, "")
    .split(/[—–:|-]/)[0]
    .trim()
    .slice(0, 80);
}

export function StartScreen() {
  const router = useRouter();
  const start = useStartJourney();
  const [name, setName] = useState("");
  const [prd, setPrd] = useState("");
  const [prdTitle, setPrdTitle] = useState("PRD");
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [key] = useState(() => newIdempotencyKey());
  const fileRef = useRef<HTMLInputElement>(null);

  const loadFile = async (file: File) => {
    setError(null);
    if (!TEXT_TYPES.some((ext) => file.name.toLowerCase().endsWith(ext))) {
      setError("Use a Markdown or plain-text file (.md or .txt), or paste the text.");
      return;
    }
    const text = await file.text();
    setPrd(text);
    setPrdTitle(file.name);
    if (!name.trim()) setName(nameFromPrd(text));
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void loadFile(file);
  };

  const ready = name.trim().length > 0 && prd.trim().length >= MIN_PRD_CHARS;

  const submit = async () => {
    if (!ready || start.isPending) return;
    setError(null);
    try {
      const result = await start.mutateAsync({
        input: { name: name.trim(), prd_title: prdTitle, prd_text: prd },
        key,
      });
      router.push(`/runs/${result.delivery_cycle_id}`);
    } catch (e) {
      setError(isApiError(e) ? e.message : e instanceof Error ? e.message : "Could not start");
    }
  };

  return (
    <SimpleShell narrow showNew={false}>
      <h1 className="sp-h1">Build a new app</h1>
      <p className="sp-lede">
        Describe what you want built. Olympus turns it into features, a design and a plan, then
        writes and tests the code. It stops to ask you before each big decision.
      </p>
      <form
        className="sp-card sp-stack"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <div className="sp-field">
          <label className="sp-label" htmlFor="sp-name">
            Project name
          </label>
          <input
            id="sp-name"
            className="sp-input"
            value={name}
            maxLength={200}
            placeholder="SupportDesk"
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className="sp-field">
          <label className="sp-label" htmlFor="sp-prd">
            Product description (PRD)
          </label>
          <div
            className="sp-drop"
            data-over={over}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={onDrop}
          >
            Drop a .md or .txt file here, or{" "}
            <button type="button" className="sp-btn sp-btn-ghost" onClick={() => fileRef.current?.click()}>
              choose a file
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".md,.markdown,.txt,text/markdown,text/plain"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void loadFile(file);
                e.target.value = "";
              }}
            />
          </div>
          <textarea
            id="sp-prd"
            className="sp-textarea sp-textarea-tall"
            value={prd}
            placeholder={
              "# My app\n\nWho it is for, what it should do, the main features and any rules.\n" +
              "Headings per feature help Olympus split the work."
            }
            onChange={(e) => {
              setPrd(e.target.value);
              if (prdTitle !== "PRD" && !e.target.value) setPrdTitle("PRD");
            }}
          />
          <span className="sp-small sp-muted">
            Plain language is fine. Mention the tech stack if you have a preference.
          </span>
        </div>

        {error && (
          <p className="sp-error" role="alert">
            {error}
          </p>
        )}

        <div className="sp-row">
          <button type="submit" className="sp-btn sp-btn-primary" disabled={!ready || start.isPending}>
            {start.isPending ? "Starting…" : "Start building"}
          </button>
          {!ready && (
            <span className="sp-small sp-muted">
              {name.trim() ? "Add a few sentences describing the app." : "Give the project a name."}
            </span>
          )}
        </div>
      </form>
    </SimpleShell>
  );
}
