"use client";

export const instant = false;

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { createDocument, listDocuments, type DocumentItem } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  BookOpen,
  FileText,
  FileWarning,
  FileCheck2,
  FolderOpen,
  Plus,
} from "lucide-react";

const TYPE_ICON: Record<string, typeof FileText> = {
  policy: FileCheck2,
  handbook: BookOpen,
  guideline: BookOpen,
  procedure: FileText,
  report: FileText,
  contract: FileWarning,
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentItem[] | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("policy");
  const [busy, setBusy] = useState(false);

  const load = () =>
    listDocuments().then(setDocs).catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  const types = useMemo(
    () => Array.from(new Set((docs ?? []).map((d) => d.document_type))),
    [docs],
  );
  const filtered = useMemo(
    () =>
      (docs ?? []).filter(
        (d) =>
          (!typeFilter || d.document_type === typeFilter) &&
          (!search || d.title.toLowerCase().includes(search.toLowerCase())),
      ),
    [docs, search, typeFilter],
  );

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await createDocument(title, docType);
      setOpen(false);
      setTitle("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Document Library</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Logical documents and their versioned revisions.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger render={<Button size="sm" />}>
            <Plus className="mr-1.5 h-4 w-4" /> New document
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create document</DialogTitle>
            </DialogHeader>
            <form onSubmit={onCreate} className="space-y-4">
              <div>
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                  className="mt-1.5"
                />
              </div>
              <div>
                <Label htmlFor="dtype">Type</Label>
                <Input
                  id="dtype"
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="mt-1.5"
                />
              </div>
              <Button type="submit" disabled={busy} className="w-full">
                {busy ? "Creating…" : "Create"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="mt-5 flex gap-3">
        <Input
          placeholder="Search titles…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-md border bg-background px-3 text-sm"
        >
          <option value="">All types</option>
          {types.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
      {!docs && (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      )}
      {docs && filtered.length === 0 && (
        <div className="mt-8 flex flex-col items-center rounded-xl border border-dashed py-12 text-center">
          <FolderOpen className="h-8 w-8 text-muted-foreground/50" />
          <p className="mt-3 text-sm font-medium">No documents match</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Create a document to start uploading versioned revisions.
          </p>
        </div>
      )}

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {filtered.map((d) => {
          const Icon = TYPE_ICON[d.document_type] ?? FileText;
          return (
            <Link key={d.id} href={`/documents/${d.id}`}>
              <Card className="group h-full transition-all hover:border-primary/40 hover:shadow-md">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                        <Icon className="h-4 w-4" />
                      </span>
                      <CardTitle className="truncate text-base">
                        {d.title}
                      </CardTitle>
                    </div>
                    <Badge variant="secondary" className="shrink-0">
                      {d.document_type}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="line-clamp-2 text-sm text-muted-foreground">
                    {d.description ?? "No description"}
                  </p>
                  <p className="mt-3 text-[11px] text-muted-foreground">
                    Updated {new Date(d.updated_at).toLocaleDateString()}
                  </p>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
