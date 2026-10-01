import { ProjectShell } from "@/components/shell/ProjectShell";
import { EventStreamProvider } from "@/lib/events/use-event-stream";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  return (
    <EventStreamProvider>
      <ProjectShell>{children}</ProjectShell>
    </EventStreamProvider>
  );
}
