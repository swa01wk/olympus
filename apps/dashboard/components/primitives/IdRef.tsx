import { cn } from "@/lib/utils";

export type IdRefProps = {
  id: string;
  muted?: boolean;
  onNavigate?: (id: string) => void;
};

export function IdRef({ id, muted, onNavigate }: IdRefProps) {
  if (!onNavigate) {
    return <span className={cn("ol-id", muted && "ol-muted")}>{id}</span>;
  }
  return (
    <button type="button" className="ol-idlink" onClick={() => onNavigate(id)}>
      {id}
    </button>
  );
}
