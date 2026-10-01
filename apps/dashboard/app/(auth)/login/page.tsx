"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { getDataMode } from "@/lib/config/data-mode";

export default function LoginPage() {
  const router = useRouter();
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
      <div className="w-full max-w-sm rounded-lg border border-[var(--border)] p-6">
        <h1 className="mb-4 text-lg font-semibold">Olympus Operator Login</h1>
        <p className="mb-4 text-xs text-[var(--muted)]">
          Mode: {getDataMode()}. Fixture login skips token validation.
        </p>
        <Button
          className="w-full"
          onClick={() => {
            document.cookie = "olympus_session=fixture; path=/";
            router.push("/projects");
          }}
        >
          Continue as lead
        </Button>
      </div>
    </div>
  );
}
