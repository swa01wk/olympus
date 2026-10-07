import type { ReactNode } from "react";
import { Button } from "./Button";

export type EmptyStateProps = {
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  children?: ReactNode;
};

export function EmptyState({ title, description, action, children }: EmptyStateProps) {
  return (
    <div className="ol-empty" role="status">
      <div className="ol-empty-mark" aria-hidden="true">
        ○
      </div>
      <h3 className="ol-section">{title}</h3>
      {description && <p>{description}</p>}
      {children}
      {action && (
        <Button variant="primary" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
