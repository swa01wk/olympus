"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { getServices } from "@/lib/api/services";
import { OlympusApiError } from "@/lib/api/errors";
import { newIdempotencyKey } from "@/lib/utils";

export function useOlympusCommand() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      cycleId: string;
      command: string;
      expected_state: string;
      payload?: unknown;
      idempotencyKey?: string;
    }) => {
      const svc = await getServices();
      return svc.deliveryCycles.command(
        input.cycleId,
        input.command,
        { expected_state: input.expected_state, payload: input.payload },
        input.idempotencyKey ?? newIdempotencyKey(),
      );
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["cycle", vars.cycleId] });
    },
    onError: (err) => {
      if (err instanceof OlympusApiError && err.status === 409) {
        qc.invalidateQueries({ queryKey: ["cycle"] });
      }
    },
  });
}
