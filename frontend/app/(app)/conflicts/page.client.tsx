"use client";



import { useEffect, useState } from "react";
import {
  detectConflicts,
  listConflicts,
  reviewConflict,
  type ConflictItem,
} from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Check, EyeOff, FileCheck, Radar } from "lucide-react";

const TYPE_LABEL: Record<string, string> = {
  contradictory: "Contradictory",
  updated_by_newer_version: "Updated by newer version",
  context_dependent: "Context dependent",
  consistent: "Consistent",
  insufficient_evidence: "Insufficient evidence",
};

export default function ConflictsPage() {
  const [items, setItems] = useState<ConflictItem[] | null>(null);
  const [filter, setFilter] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanMsg, setScanMsg] = useState<string | null>(null);

  const load = () =>
    listConflicts(filter || undefined)
      .then(setItems)
      .catch((e) => setError(e.message));

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  async function runDetection() {
    setBusy("detect");
    setScanMsg(null);
    try {
      const r = await detectConflicts();
      setScanMsg(`Detection complete — ${r.findings.length} finding(s).`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Detection failed");
    } finally {
      setBusy(null);
    }
  }

  async function review(id: string, action: "confirm" | "dismiss" | "resolve") {
    setBusy(id);
    try {
      await reviewConflict(id, action, note || undefined);
      setNote("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Conflicts</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Contradictory rules across documents — reviewed by humans, never
            silently resolved.
          </p>
        </div>
        <Button size="sm" onClick={runDetection} disabled={busy === "detect"}>
          <Radar className="mr-1.5 h-4 w-4" />
          {busy === "detect" ? "Scanning…" : "Run detection"}
        </Button>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          <option value="potential">Potential</option>
          <option value="confirmed">Confirmed</option>
          <option value="dismissed">Dismissed</option>
          <option value="resolved">Resolved</option>
        </select>
        {scanMsg && <p className="text-xs text-muted-foreground">{scanMsg}</p>}
        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>

      {!items && (
        <div className="mt-6 space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      )}
      {items?.length === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">
          No conflicts on record. Run detection to scan eligible versions.
        </p>
      )}

      <div className="mt-6 space-y-3">
        {items?.map((c) => (
          <Card key={c.id}>
            <CardContent className="py-4">
              <button
                className="w-full text-left"
                onClick={() => setExpanded(expanded === c.id ? null : c.id)}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    variant={c.conflict_type === "contradictory" ? "destructive" : "secondary"}
                  >
                    {TYPE_LABEL[c.conflict_type] ?? c.conflict_type}
                  </Badge>
                  <Badge variant="outline">{c.status}</Badge>
                  {c.confidence != null && (
                    <span className="text-[11px] text-muted-foreground">
                      confidence {c.confidence.toFixed(2)}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm">{c.explanation}</p>
              </button>

              {expanded === c.id && (
                <div className="mt-4 border-t pt-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-md bg-muted/50 p-3">
                      <p className="mb-1 text-[11px] font-medium text-muted-foreground">
                        Evidence A
                      </p>
                      <p className="whitespace-pre-wrap text-xs">{c.evidence_a}</p>
                    </div>
                    <div className="rounded-md bg-muted/50 p-3">
                      <p className="mb-1 text-[11px] font-medium text-muted-foreground">
                        Evidence B
                      </p>
                      <p className="whitespace-pre-wrap text-xs">{c.evidence_b}</p>
                    </div>
                  </div>
                  {c.resolution_note && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      Reviewer note: {c.resolution_note}
                    </p>
                  )}
                  {(c.status === "potential" || c.status === "confirmed") && (
                    <div className="mt-4 flex items-end gap-2">
                      <div className="flex-1">
                        <Input
                          placeholder="Resolution note (optional)"
                          value={note}
                          onChange={(e) => setNote(e.target.value)}
                          className="h-8 text-xs"
                        />
                      </div>
                      <Button size="sm" variant="outline" disabled={busy === c.id}
                        onClick={() => review(c.id, "confirm")}>
                        <FileCheck className="mr-1 h-3.5 w-3.5" /> Confirm
                      </Button>
                      <Button size="sm" variant="outline" disabled={busy === c.id}
                        onClick={() => review(c.id, "dismiss")}>
                        <EyeOff className="mr-1 h-3.5 w-3.5" /> Dismiss
                      </Button>
                      <Button size="sm" disabled={busy === c.id}
                        onClick={() => review(c.id, "resolve")}>
                        <Check className="mr-1 h-3.5 w-3.5" /> Resolve
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
