"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getDashboardStats,
  listConflicts,
  type ConflictItem,
  type DashboardStats,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertTriangle, FileText, GitBranch, Layers, MessagesSquare } from "lucide-react";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getDashboardStats(), listConflicts()])
      .then(([s, c]) => {
        setStats(s);
        setConflicts(c.slice(0, 5));
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return <p className="p-8 text-sm text-destructive">{error}</p>;
  }
  if (!stats) {
    return (
      <div className="grid gap-4 p-8 md:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
    );
  }

  const cards = [
    { label: "Documents", value: stats.documents, icon: FileText },
    { label: "Versions", value: stats.versions, icon: GitBranch },
    { label: "Indexed chunks", value: stats.chunks, icon: Layers },
    { label: "Open conflicts", value: stats.open_conflicts, icon: AlertTriangle, warn: stats.open_conflicts > 0 },
    { label: "Ingestion failures", value: stats.ingestion_failures, icon: AlertTriangle, warn: stats.ingestion_failures > 0 },
    { label: "My chat sessions", value: stats.my_chat_sessions, icon: MessagesSquare },
  ];

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Corpus state at a glance — scoped to documents you can access.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map(({ label, value, icon: Icon, warn }) => (
          <Card key={label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {label}
              </CardTitle>
              <Icon className={`h-4 w-4 ${warn ? "text-amber-500" : "text-muted-foreground"}`} />
            </CardHeader>
            <CardContent>
              <p className={`text-3xl font-semibold ${warn ? "text-amber-600" : ""}`}>
                {value}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Versions by status</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {Object.entries(stats.versions_by_status).length === 0 && (
              <p className="text-sm text-muted-foreground">No versions yet.</p>
            )}
            {Object.entries(stats.versions_by_status).map(([status, count]) => (
              <Badge key={status} variant="secondary" className="px-3 py-1 text-xs">
                {status}: {count}
              </Badge>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Open conflicts</CardTitle>
            <Link href="/conflicts" className="text-xs text-blue-700 hover:underline">
              Review all →
            </Link>
          </CardHeader>
          <CardContent className="space-y-2">
            {conflicts.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No conflicts detected. Run detection from the Conflicts page.
              </p>
            )}
            {conflicts.map((c) => (
              <div key={c.id} className="rounded-md border p-2.5 text-xs">
                <div className="flex items-center gap-2">
                  <Badge variant={c.status === "confirmed" ? "destructive" : "secondary"}>
                    {c.conflict_type}
                  </Badge>
                  <Badge variant="outline">{c.status}</Badge>
                </div>
                <p className="mt-1.5 line-clamp-2 text-muted-foreground">{c.explanation}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
