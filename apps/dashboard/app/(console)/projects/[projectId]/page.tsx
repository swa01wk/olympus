import { ProjectOverviewClient } from "@/components/screens/ProjectOverviewClient";

export default async function ProjectOverviewPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ProjectOverviewClient projectId={projectId} />;
}
