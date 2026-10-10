"use client";

import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "@/lib/api";

type Status =
  | { kind: "loading" }
  | { kind: "ok"; health: HealthResponse }
  | { kind: "error"; message: string };

export function BackendStatus() {
  const [status, setStatus] = useState<Status>({ kind: "loading" });

  useEffect(() => {
    getHealth()
      .then((health) => setStatus({ kind: "ok", health }))
      .catch((err: unknown) =>
        setStatus({
          kind: "error",
          message: err instanceof Error ? err.message : "Unknown error",
        }),
      );
  }, []);

  const dot =
    status.kind === "ok"
      ? "bg-emerald-500"
      : status.kind === "error"
        ? "bg-red-500"
        : "bg-amber-400 animate-pulse";

  const label =
    status.kind === "ok"
      ? `API connected — v${status.health.version}`
      : status.kind === "error"
        ? "API unreachable"
        : "Checking API…";

  return (
    <div
      className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-1.5 text-sm text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
      title={status.kind === "error" ? status.message : undefined}
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden />
      <span>{label}</span>
    </div>
  );
}
