"use client";

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
import { Plus } from "lucide-react";

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
        <p className="mt-8 text-sm text-muted-foreground">
          No documents match. Create one to start uploading revisions.
        </p>
      )}

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {filtered.map((d) => (
          <Link key={d.id} href={`/documents/${d.id}`}>
            <Card className="h-full transition-colors hover:border-primary/50">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{d.title}</CardTitle>
                  <Badge variant="secondary">{d.document_type}</Badge>
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
        ))}
      </div>
    </div>
  );
}
