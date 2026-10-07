"use client";

import { screenHref } from "@/lib/nav-hrefs";
import { presentationForUiKey } from "@/src/adapters/status";
import { SCREENS, type LaneId, type ScreenId } from "@/src/control-plane/lanes";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const DRILL_SCREENS: ScreenId[] = ["S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10"];

export function NavRail({
  projectId,
  cycleId,
  laneFlags,
}: {
  projectId: string;
  cycleId: string;
  laneFlags?: Partial<Record<LaneId, string>>;
}) {
  const pathname = usePathname();

  const studioPath = `/projects/${projectId}/cycles/${cycleId}/studio`;

  const isActive = (screen: ScreenId | "INT" | "AUD" | "STU") => {
    if (screen === "STU") {
      return pathname === studioPath || pathname.startsWith(`${studioPath}/`);
    }
    if (screen === "S02") {
      return (
        pathname === `/projects/${projectId}/cycles/${cycleId}` ||
        pathname === `/projects/${projectId}/cycles/${cycleId}/`
      );
    }
    const href = screenHref(screen, projectId, cycleId);
    const base = href.split("?")[0];
    return pathname === href || pathname.startsWith(base);
  };

  const item = (screen: ScreenId) => {
    const s = SCREENS.find((x: (typeof SCREENS)[number]) => x.id === screen)!;
    const flag = s.lane ? laneFlags?.[s.lane as LaneId] : undefined;
    const href = screenHref(screen, projectId, cycleId);
    return (
      <Link
        key={screen}
        href={href}
        className={cn("ol-rail-i", isActive(screen) && "is-on", screen === "S02" && "is-hub")}
        aria-current={isActive(screen) ? "page" : undefined}
        title={`${s.num} · ${s.name}`}
      >
        <span className="ol-rail-mono">{s.mono}</span>
        <span className="ol-rail-t">{s.short}</span>
        {flag && (
          <span
            className={cn("ol-rail-flag", `ol-tc-${presentationForUiKey(flag).tone}`)}
            aria-label="needs attention"
          >
            {presentationForUiKey(flag).glyph}
          </span>
        )}
      </Link>
    );
  };

  return (
    <nav className="ol-rail" aria-label="Workspace">
      {item("S01")}
      {item("S02")}
      <Link
        href={studioPath}
        className={cn("ol-rail-i", isActive("STU") && "is-on")}
        aria-current={isActive("STU") ? "page" : undefined}
        title="Studio · chat and workspace"
      >
        <span className="ol-rail-mono">STU</span>
        <span className="ol-rail-t">Studio</span>
      </Link>
      <div className="ol-rail-div" aria-hidden="true">
        <span>drill</span>
      </div>
      {DRILL_SCREENS.map(item)}
      <div className="ol-rail-spacer" />
      <Link
        href={screenHref("INT", projectId, cycleId)}
        className={cn("ol-rail-i ol-rail-util", isActive("INT") && "is-on")}
        title="Integrations"
      >
        <span className="ol-rail-mono">IO</span>
        <span className="ol-rail-t">Integr.</span>
      </Link>
      <Link
        href={screenHref("AUD", projectId, cycleId)}
        className={cn("ol-rail-i ol-rail-util", isActive("AUD") && "is-on")}
        title="Audit history"
      >
        <span className="ol-rail-mono">AU</span>
        <span className="ol-rail-t">Audit</span>
      </Link>
    </nav>
  );
}
