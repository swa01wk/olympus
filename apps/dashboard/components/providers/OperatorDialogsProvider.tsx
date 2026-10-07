"use client";

import { ApprovalDialog } from "@/components/dialogs/ApprovalDialog";
import { CheckpointDialog } from "@/components/dialogs/CheckpointDialog";
import {
  CycleCommandDialog,
  type CycleCommandRequest,
} from "@/components/dialogs/CycleCommandDialog";
import { IntakeFormDialog } from "@/components/dialogs/IntakeFormDialog";
import { AskOlympusDrawer } from "@/components/shell/AskOlympusDrawer";
import type { AttentionItem } from "@/src/control-plane/attention";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type ShellContext = {
  projectId: string;
  cycleId: string;
};

type OperatorDialogsValue = {
  setShellContext: (ctx: ShellContext) => void;
  openIntake: () => void;
  openAskOlympus: () => void;
  openAttentionItem: (item: AttentionItem) => void;
  openCycleCommand: (req: CycleCommandRequest) => void;
};

const OperatorDialogsContext = createContext<OperatorDialogsValue | null>(null);

export function useOperatorDialogs(): OperatorDialogsValue {
  const ctx = useContext(OperatorDialogsContext);
  if (!ctx) {
    throw new Error("useOperatorDialogs must be used within OperatorDialogsProvider");
  }
  return ctx;
}

export function OperatorDialogsProvider({ children }: { children: ReactNode }) {
  const [shell, setShell] = useState<ShellContext>({ projectId: "", cycleId: "" });
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [askOpen, setAskOpen] = useState(false);
  const [approvalId, setApprovalId] = useState<string | null>(null);
  const [clarificationId, setClarificationId] = useState<string | null>(null);
  const [cycleCommand, setCycleCommand] = useState<CycleCommandRequest | null>(null);

  const setShellContext = useCallback((ctx: ShellContext) => {
    setShell(ctx);
  }, []);

  const openAttentionItem = useCallback((item: AttentionItem) => {
    if (item.kind === "APPROVAL") setApprovalId(item.id);
    else if (item.kind === "CLARIFICATION") setClarificationId(item.id);
  }, []);

  const value = useMemo(
    () => ({
      setShellContext,
      openIntake: () => setIntakeOpen(true),
      openAskOlympus: () => setAskOpen(true),
      openAttentionItem,
      openCycleCommand: setCycleCommand,
    }),
    [setShellContext, openAttentionItem],
  );

  return (
    <OperatorDialogsContext.Provider value={value}>
      {children}
      <IntakeFormDialog
        open={intakeOpen}
        projectId={shell.projectId || null}
        onClose={() => setIntakeOpen(false)}
      />
      <AskOlympusDrawer
        open={askOpen}
        onClose={() => setAskOpen(false)}
        projectId={shell.projectId || null}
        cycleId={shell.cycleId || null}
      />
      <ApprovalDialog
        open={Boolean(approvalId)}
        approvalId={approvalId}
        onClose={() => setApprovalId(null)}
      />
      <CheckpointDialog
        open={Boolean(clarificationId)}
        clarificationId={clarificationId}
        onClose={() => setClarificationId(null)}
      />
      <CycleCommandDialog
        open={Boolean(cycleCommand)}
        request={cycleCommand}
        onClose={() => setCycleCommand(null)}
      />
    </OperatorDialogsContext.Provider>
  );
}
