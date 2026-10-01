import { redirect } from "next/navigation";

export default async function LineageRedirect({
  searchParams,
}: {
  searchParams: Promise<{ project?: string }>;
}) {
  const params = await searchParams;
  const project = params.project ?? "11111111-1111-4111-8111-111111111101";
  redirect(`/projects/${project}/lineage`);
}
