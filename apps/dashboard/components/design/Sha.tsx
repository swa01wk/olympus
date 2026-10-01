import { formatShortSha } from "@/lib/utils/sha";

export function Sha({
  sha,
  role,
  className,
}: {
  sha: string | null | undefined;
  role?: string;
  className?: string;
}) {
  if (!sha) return <span className={className}>—</span>;
  return (
    <span
      className={`font-mono ${className ?? ""}`}
      data-testid="sha"
      data-sha={sha}
      data-sha-role={role}
      title={sha}
    >
      {formatShortSha(sha)}
    </span>
  );
}
