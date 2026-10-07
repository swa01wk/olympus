import { ExecutionDetailScreen } from "@/components/screens/ExecutionDetailScreen";

export default async function ExecutionPage({
  params,
}: {
  params: Promise<{ executionId: string }>;
}) {
  const { executionId } = await params;
  return <ExecutionDetailScreen executionId={executionId} />;
}
