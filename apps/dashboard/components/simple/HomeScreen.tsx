"use client";

import { AutopilotPill } from "@/components/simple/AutopilotPill";
import { SimpleShell } from "@/components/simple/SimpleShell";
import { journeyName } from "@/lib/journey-progress";
import { isApiError } from "@/src/api/client";
import { setAccessToken } from "@/src/api/config";
import { useHome } from "@/src/api/hooks/use-autopilot";
import type { HomeProject } from "@/src/api/types/autopilot";
import Link from "next/link";

const COMING_SOON = [
  { title: "Add a feature", body: "Describe a change to a project Olympus built or learned." },
  { title: "Fix a bug", body: "Olympus reproduces it, fixes it and proves the fix." },
];

/** `olympus start` in any folder: new folder + PRD.md → new app; existing code → onboarding. */
function FromTerminal() {
  return (
    <div className="sp-choice" style={{ gridColumn: "1 / -1" }}>
      <div className="sp-choice-title">Or start from your project folder</div>
      <ol className="sp-steps sp-small">
        <li>
          Once: <code className="sp-code">make install-cli</code> in the Olympus folder
        </li>
        <li>
          In your project: <code className="sp-code">cd ~/code/my-app &amp;&amp; olympus start</code>
        </li>
      </ol>
      <div className="sp-small sp-muted">
        Existing code: Olympus copies and learns it, and never edits your folder. Empty folder
        with a PRD.md: it builds the app and hands the code back on an{" "}
        <code className="sp-code">olympus/…</code> branch.
      </div>
    </div>
  );
}

export function HomeScreen() {
  const home = useHome();

  return (
    <SimpleShell>
      {home.isLoading && <p className="sp-muted">Loading…</p>}
      {home.isError && <ConnectionProblem error={home.error} />}
      {home.data && home.data.length === 0 && <Welcome />}
      {home.data && home.data.length > 0 && <ProjectList projects={home.data} />}
    </SimpleShell>
  );
}

function ProjectList({ projects }: { projects: HomeProject[] }) {
  const waiting = projects.filter((p) => p.latest_run?.autopilot.status === "NEEDS_YOU").length;
  return (
    <>
      <div className="sp-home-head">
        <div>
          <h1 className="sp-h1">Your projects</h1>
          <p className="sp-lede" style={{ margin: 0 }}>
            {waiting > 0
              ? `${waiting} ${waiting === 1 ? "project needs" : "projects need"} you.`
              : "Nothing needs you right now."}
          </p>
        </div>
        <Link href="/new" className="sp-btn sp-btn-primary">
          Build a new app
        </Link>
      </div>
      <ul className="sp-project-list">
        {projects.map((p) => (
          <li key={p.id}>
            <ProjectRow project={p} />
          </li>
        ))}
      </ul>
      <div className="sp-choices">
        <FromTerminal />
      </div>
    </>
  );
}

function ProjectRow({ project }: { project: HomeProject }) {
  const run = project.latest_run;
  const href = run ? `/runs/${run.delivery_cycle_id}` : `/projects/${project.id}`;
  return (
    <Link href={href} className="sp-project">
      <div>
        <div className="sp-project-name">{project.name}</div>
        {run && (
          <div className="sp-small sp-muted">
            {journeyName(run.type)}
            {project.local_path && <> · {project.local_path}</>}
          </div>
        )}
      </div>
      {run && <AutopilotPill status={run.autopilot.status} />}
      <div className="sp-project-msg">
        {run
          ? run.autopilot.status === "OFF"
            ? `Autopilot is off · stage ${run.state.replace(/_/g, " ").toLowerCase()}`
            : run.autopilot.message
          : "No runs yet"}
      </div>
    </Link>
  );
}

function Welcome() {
  return (
    <div className="sp-empty">
      <h1 className="sp-h1">Build something</h1>
      <p className="sp-lede">
        Give Olympus a product description. It plans the work, writes and tests the code, and asks
        you only when a decision is yours.
      </p>
      <Link href="/new" className="sp-btn sp-btn-primary">
        Build a new app from a PRD
      </Link>
      <div className="sp-choices">
        <FromTerminal />
        {COMING_SOON.map((c) => (
          <div key={c.title} className="sp-choice" aria-disabled="true">
            <div className="sp-choice-title">{c.title}</div>
            <div className="sp-small sp-muted">{c.body}</div>
            <div className="sp-small sp-muted" style={{ marginTop: 6 }}>
              Coming soon
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConnectionProblem({ error }: { error: unknown }) {
  const unauthorized = isApiError(error) && (error.status === 401 || error.status === 403);
  return (
    <div className="sp-card sp-stack">
      <h1 className="sp-h1">Can’t reach Olympus</h1>
      {unauthorized ? (
        <>
          <p className="sp-lede" style={{ margin: 0 }}>
            This browser isn’t signed in. Restart with <code className="sp-code">make dev</code>; it
            signs you in automatically. If you signed in by hand before, forget that sign-in.
          </p>
          <div>
            <button
              type="button"
              className="sp-btn"
              onClick={() => {
                setAccessToken(null);
                window.location.reload();
              }}
            >
              Forget saved sign-in
            </button>
          </div>
        </>
      ) : (
        <p className="sp-lede" style={{ margin: 0 }}>
          The API isn’t responding. Start everything with <code className="sp-code">make dev</code>{" "}
          from the project folder.
        </p>
      )}
      <p className="sp-small sp-muted" style={{ margin: 0 }}>
        {error instanceof Error ? error.message : String(error)}
      </p>
    </div>
  );
}
