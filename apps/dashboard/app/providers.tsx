"use client";

import { OperatorDialogsProvider } from "@/components/providers/OperatorDialogsProvider";
import { QueryProvider } from "@/components/providers/QueryProvider";
import type { ReactNode } from "react";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryProvider>
      <OperatorDialogsProvider>{children}</OperatorDialogsProvider>
    </QueryProvider>
  );
}
