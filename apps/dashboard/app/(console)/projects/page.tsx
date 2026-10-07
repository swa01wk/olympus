"use client";

import { EmptyState, Panel } from "@/components/primitives";
import { useProjects } from "@/src/api/hooks/use-olympus-queries";
import Link from "next/link";

export default function ProjectsIndexPage() {
  const projects = useProjects();

  return (
    <div className="ol-app ol-main">
      <h1 className="ol-title">Projects</h1>
      {projects.isLoading && <p className="ol-muted">Loading…</p>}
      {projects.isError && (
        <EmptyState
          title="Sign in required"
          description="Set olympus_api_token in localStorage or NEXT_PUBLIC_OLYMPUS_API_TOKEN."
        />
      )}
      <ul className="list-none p-0 m-0 flex flex-col gap-2">
        {(projects.data ?? []).map((p) => (
          <li key={p.id}>
            <Link className="ol-idlink text-base" href={`/projects/${p.id}`}>
              {p.key} — {p.name}
            </Link>
          </li>
        ))}
      </ul>
      {!projects.isLoading && projects.data?.length === 0 && (
        <Panel title="No projects">
          <p className="ol-muted text-sm m-0">Create a project through the Control API.</p>
        </Panel>
      )}
    </div>
  );
}
