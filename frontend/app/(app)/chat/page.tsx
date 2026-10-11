"use client";

import { useState } from "react";
import { askChat, type ChatAnswer } from "@/lib/api";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AlertTriangle, CalendarClock, Send } from "lucide-react";

interface Turn {
  question: string;
  result: ChatAnswer;
}

const INTENT_LABEL: Record<string, string> = {
  current: "current",
  as_of: "as-of date",
  compare: "comparison",
};

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [asOf, setAsOf] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await askChat(question.trim(), {
        sessionId,
        asOfDate: asOf || undefined,
      });
      setSessionId(result.session_id);
      setTurns((t) => [...t, { question: question.trim(), result }]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Ask</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Temporal questions answered only from versions valid at the requested time.
        </p>
      </div>

      <div className="mt-6 flex-1 space-y-6 overflow-y-auto pb-4">
        {turns.length === 0 && (
          <Card className="border-dashed">
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              Try: “What is the current annual leave allowance?”, “What was it in
              February 2025?”, or “What changed between 2024 and 2026?”
            </CardContent>
          </Card>
        )}

        {turns.map((t, i) => (
          <div key={i} className="space-y-3">
            <div className="flex justify-end">
              <p className="max-w-xl rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground">
                {t.question}
              </p>
            </div>
            <Card>
              <CardHeader className="pb-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">
                    {INTENT_LABEL[t.result.intent.kind] ?? t.result.intent.kind}
                  </Badge>
                  {t.result.intent.as_of && (
                    <Badge variant="outline">
                      <CalendarClock className="mr-1 h-3 w-3" />
                      as of {t.result.intent.as_of}
                    </Badge>
                  )}
                  {t.result.intent.compare_a && (
                    <Badge variant="outline">
                      {t.result.intent.compare_a} vs {t.result.intent.compare_b}
                    </Badge>
                  )}
                  <Badge variant={t.result.status === "answered" ? "default" : "destructive"}>
                    {t.result.status === "answered" ? "answered" : "insufficient evidence"}
                  </Badge>
                  {t.result.intent.ambiguous && (
                    <Badge variant="outline">date ambiguity</Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {t.result.warnings.length > 0 && (
                  <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                    <AlertTriangle className="mr-1.5 inline h-3.5 w-3.5" />
                    {t.result.warnings.map((w, j) => (
                      <p key={j}>{w}</p>
                    ))}
                  </div>
                )}
                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                  {t.result.answer}
                </p>
                {t.result.citations.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs font-medium text-muted-foreground">
                      Sources — which versions answered this
                    </p>
                    <div className="space-y-2">
                      {t.result.citations.map((c) => (
                        <div key={c.chunk_id} className="rounded-md border p-2.5 text-xs">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">{c.document_title}</span>
                            <Badge variant="secondary">v{c.version_number}</Badge>
                            <span className="text-muted-foreground">
                              effective {c.effective_from} → {c.effective_until ?? "present"}
                            </span>
                            {c.page_number && (
                              <span className="text-muted-foreground">· p.{c.page_number}</span>
                            )}
                            {c.section_title && (
                              <span className="text-muted-foreground">· {c.section_title}</span>
                            )}
                            <span className="ml-auto text-muted-foreground">
                              score {c.score.toFixed(2)}
                            </span>
                          </div>
                          <p className="mt-1.5 line-clamp-2 text-muted-foreground">
                            {c.content}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {t.result.status === "answered" &&
                  t.result.evidence.length > t.result.citations.length && (
                    <p className="text-[11px] text-muted-foreground">
                      + {t.result.evidence.length - t.result.citations.length} more
                      retrieved passage(s) not cited
                    </p>
                  )}
              </CardContent>
            </Card>
          </div>
        ))}
      </div>

      {error && <p className="pb-2 text-sm text-destructive">{error}</p>}

      <form onSubmit={submit} className="border-t pt-4">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <Label htmlFor="q" className="sr-only">Question</Label>
            <Textarea
              id="q"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about a policy — current, historical, or comparative…"
              rows={2}
              className="resize-none"
            />
          </div>
          <div className="w-40">
            <Label htmlFor="asof" className="text-xs text-muted-foreground">
              As-of date (optional)
            </Label>
            <Input
              id="asof"
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              className="mt-1"
            />
          </div>
          <Button type="submit" disabled={busy || !question.trim()}>
            <Send className="mr-1.5 h-4 w-4" />
            {busy ? "…" : "Ask"}
          </Button>
        </div>
      </form>
    </div>
  );
}
