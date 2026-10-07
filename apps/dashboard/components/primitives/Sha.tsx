export type ShaProps = {
  value: string;
  label?: string;
  historical?: boolean;
};

export function Sha({ value, label, historical }: ShaProps) {
  const className = historical ? "ol-sha line-through opacity-80" : "ol-sha";
  return (
    <span className={className}>
      {label && <span className="ol-sha-l">{label}</span>}
      {value}
    </span>
  );
}
