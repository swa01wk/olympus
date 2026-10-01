import { redirect } from "next/navigation";

export default async function RepositoryRedirect({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  redirect(`/projects/${projectId}/code?tab=repository`);
}
