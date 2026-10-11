"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  approveVersion,
  compareVersions,
  getDocument,
  rejectVersion,
  uploadVersion,
  type CompareResult,
  type DocumentItem,
  type VersionItem,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Check, GitCompare, Upload, X } from "lucide-react";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  approved: "default",
  pending_review: "secondary",
  superseded: "outline",
  archived: "outline",
  draft: "outline",
};

function fmtRange(v: VersionItem) {
  return `${v.effective_from} → ${v.effective_until ?? "present"}`;
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<(DocumentItem & { versions: VersionItem[] }) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [effFrom, setEffFrom] = useState("");
  const [effUntil, setEffUntil] = useState("");
  const [supersedeId, setSupersedeId] = useState<string | null>(null);

  const load = () =>
    getDocument(id).then(setDoc).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error) return <p className="p-8 text-sm text-destructive">{error}</p>;
  if (!doc) return <div className="p-8"><Skeleton className="h-64" /></div>;

  const versions = [...doc.versions].sort((a, b) => b.version_number - a.version_number);
  const approved = versions.filter((v) => v.status === "approved");

  async function doApprove(v: VersionItem) {
    setBusy(v.id);
    try {
      // If exactly one other approved version exists, offer to supersede it.
      const others = approved.filter((x) => x.id !== v.id);
      await approveVersion(v.id, supersedeId ?? (others.length === 1 ? others[0].id : undefined));
      setSupersedeId(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusy(null);
    }
  }

  async function doReject(v: VersionItem) {
    setBusy(v.id);
    try {
      await rejectVersion(v.id, "Rejected via UI");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setBusy(null);
    }
  }

  function toggleCompare(versionId: string) {
    setSelected((sel) =>
      sel.includes(versionId)
        ? sel.filter((s) => s !== versionId)
        : [...sel, versionId].slice(-2),
    );
  }

  async function runCompare() {
    if (selected.length !== 2) return;
    setBusy("compare");
    try {
      setCompare(await compareVersions(selected[0], selected[1]));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Compare failed");
    } finally {
      setBusy(null);
    }
  }

  async function doUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !effFrom) return;
    setBusy("upload");
    try {
      await uploadVersion(id, file, effFrom, effUntil || undefined);
      setUploadOpen(false);
      setFile(null);
      setEffFrom("");
      setEffUntil("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="p-8">
      <Link href="/documents" className="text-xs text-muted-foreground hover:text-foreground">
        ← Library
      </Link>
      <div className="mt-2 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{doc.title}</h1>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant="secondary">{doc.document_type}</Badge>
            <span className="text-xs text-muted-foreground">
              {versions.length} version{versions.length === 1 ? "" : "s"}
            </span>
          </div>
        </div>
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogTrigger render={<Button size="sm" />}>
            <Upload className="mr-1.5 h-4 w-4" /> Upload revision
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Upload new revision</DialogTitle></DialogHeader>
            <form onSubmit={doUpload} className="space-y-4">
              <div>
                <Label htmlFor="file">File (PDF, DOCX, TXT)</Label>
                <Input id="file" type="file" accept=".pdf,.docx,.txt" required
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mt-1.5" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="from">Effective from</Label>
                  <Input id="from" type="date" value={effFrom} required
                    onChange={(e) => setEffFrom(e.target.value)} className="mt-1.5" />
                </div>
                <div>
                  <Label htmlFor="until">Effective until (optional)</Label>
                  <Input id="until" type="date" value={effUntil}
                    onChange={(e) => setEffUntil(e.target.value)} className="mt-1.5" />
                </div>
              </div>
              <Button type="submit" disabled={busy === "upload"} className="w-full">
                {busy === "upload" ? "Uploading & ingesting…" : "Upload"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Separator className="my-5" />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Revision timeline */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Revision timeline</CardTitle>
            {selected.length === 2 && (
              <Button size="sm" variant="outline" onClick={runCompare} disabled={busy === "compare"}>
                <GitCompare className="mr-1.5 h-4 w-4" />
                {busy === "compare" ? "Comparing…" : "Compare selected"}
              </Button>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            {versions.length === 0 && (
              <p className="text-sm text-muted-foreground">No revisions yet — upload the first.</p>
            )}
            {versions.map((v) => (
              <div key={v.id} className="rounded-md border p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selected.includes(v.id)}
                      onChange={() => toggleCompare(v.id)}
                      className="h-3.5 w-3.5"
                      title="Select for comparison"
                    />
                    <span className="text-sm font-medium">v{v.version_number}</span>
                    <Badge variant={STATUS_VARIANT[v.status] ?? "outline"}>{v.status}</Badge>
                    <Badge variant={v.ingestion_status === "completed" ? "secondary" : v.ingestion_status === "failed" ? "destructive" : "outline"}>
                      {v.ingestion_status}
                    </Badge>
                  </div>
                  {v.status === "pending_review" && (
                    <div className="flex gap-1">
                      <Button size="sm" variant="outline" className="h-7 px-2"
                        disabled={busy === v.id || v.ingestion_status !== "completed"}
                        onClick={() => doApprove(v)}>
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="outline" className="h-7 px-2"
                        disabled={busy === v.id} onClick={() => doReject(v)}>
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {v.original_filename} · effective {fmtRange(v)}
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Uploaded {new Date(v.uploaded_at).toLocaleDateString()}
                  {v.approved_at && ` · approved ${new Date(v.approved_at).toLocaleDateString()}`}
                  {typeof v.extra?.chunk_count === "number" && ` · ${v.extra.chunk_count} chunks`}
                </p>
                {v.ingestion_status === "failed" && (
                  <p className="mt-1 text-[11px] text-destructive">
                    {String(v.extra?.ingestion_error ?? "ingestion failed")}
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Compare result */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Version comparison</CardTitle>
          </CardHeader>
          <CardContent>
            {!compare && (
              <p className="text-sm text-muted-foreground">
                Select two versions on the left and click Compare to see the
                paragraph-level diff between revisions.
              </p>
            )}
            {compare && (
              <div className="space-y-4 text-sm">
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span>
                    A: v{compare.version_a.version_number} (
                    {compare.version_a.effective_from} → {compare.version_a.effective_until ?? "present"})
                  </span>
                  <span>
                    B: v{compare.version_b.version_number} (
                    {compare.version_b.effective_from} → {compare.version_b.effective_until ?? "present"})
                  </span>
                </div>
                {!compare.changed_hint && (
                  <p className="text-muted-foreground">No differences found.</p>
                )}
                {compare.removed.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-destructive">Removed in B</p>
                    {compare.removed.map((t, i) => (
                      <p key={i} className="mb-1 rounded bg-red-50 px-2 py-1.5 text-xs line-through decoration-red-400 dark:bg-red-950/40">
                        {t}
                      </p>
                    ))}
                  </div>
                )}
                {compare.added.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-emerald-700">Added in B</p>
                    {compare.added.map((t, i) => (
                      <p key={i} className="mb-1 rounded bg-emerald-50 px-2 py-1.5 text-xs dark:bg-emerald-950/40">
                        {t}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
