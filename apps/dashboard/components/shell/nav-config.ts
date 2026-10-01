export type NavItem = { href: string; label: string; match?: RegExp };

export type NavGroup = { id: string; label: string; items: NavItem[] };

export function projectNav(projectId: string, cycleId: string | null): NavGroup[] {
  const c = cycleId ?? "";
  const cycleQ = c ? `?cycle=${c}` : "";
  return [
    {
      id: "delivery",
      label: "Delivery",
      items: [
        { href: `/projects/${projectId}`, label: "Command Center" },
        { href: `/projects/${projectId}/control-plane${cycleQ}`, label: "Control Plane" },
        {
          href: c
            ? `/projects/${projectId}/cycles/${c}/tasks${cycleQ}`
            : `/projects/${projectId}/cycles`,
          label: "Tasks",
        },
        { href: `/projects/${projectId}/executions${cycleQ}`, label: "Executions" },
      ],
    },
    {
      id: "product",
      label: "Product",
      items: [{ href: `/projects/${projectId}/product${cycleQ}`, label: "Product & Specs" }],
    },
    {
      id: "operations",
      label: "Operations",
      items: [
        { href: `/projects/${projectId}/agents${cycleQ}`, label: "Agents" },
        { href: `/projects/${projectId}/agents?tab=runtime${c ? `&cycle=${c}` : ""}`, label: "Runtime" },
        { href: `/projects/${projectId}/agents?tab=actions${c ? `&cycle=${c}` : ""}`, label: "Actions" },
      ],
    },
    {
      id: "intelligence",
      label: "Intelligence",
      items: [
        { href: `/projects/${projectId}/code${cycleQ}`, label: "Code Intelligence" },
        { href: `/projects/${projectId}/lineage${cycleQ}`, label: "Lineage" },
        { href: `/projects/${projectId}/impact${cycleQ}`, label: "Impact" },
        { href: `/projects/${projectId}/brownfield${cycleQ}`, label: "Brownfield" },
      ],
    },
    {
      id: "assurance",
      label: "Assurance",
      items: [
        {
          href: c
            ? `/projects/${projectId}/cycles/${c}/integration${cycleQ}`
            : `/projects/${projectId}/assurance${cycleQ}`,
          label: "Integration",
        },
        { href: `/projects/${projectId}/assurance?tab=evidence${c ? `&cycle=${c}` : ""}`, label: "Evidence" },
        { href: `/projects/${projectId}/assurance?tab=findings${c ? `&cycle=${c}` : ""}`, label: "Findings" },
        { href: `/projects/${projectId}/assurance?tab=gates${c ? `&cycle=${c}` : ""}`, label: "Gates" },
      ],
    },
    {
      id: "governance",
      label: "Governance",
      items: [
        { href: `/inbox?project=${projectId}`, label: "Human Attention" },
        { href: `/projects/${projectId}/releases${cycleQ}`, label: "Release" },
      ],
    },
    {
      id: "system",
      label: "System",
      items: [
        { href: `/projects/${projectId}/integrations${cycleQ}`, label: "Integrations" },
        { href: `/audit?project=${projectId}${c ? `&cycle=${c}` : ""}`, label: "Audit" },
      ],
    },
  ];
}
