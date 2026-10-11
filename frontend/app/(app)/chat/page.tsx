"use client";

export const instant = false;

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  askChat,
  getChatSession,
  listChatSessions,
  type ChatAnswer,
  type ChatSessionItem,
} from "@/lib/api";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertTriangle,
  CalendarClock,
  History,
  Plus,
  Send,
} from "lucide-react";

interface Turn {
  question: string;
  result: ChatAnswer;
}

const INTENT_LABEL: Record<string, string> = {
  current: "current",
  as_of: "as-of date",
  compare: "comparison",
  history: "saved",
};

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [asOf, setAsOf] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshSessions() {
    try {
      setSessions(await listChatSessions());
    } catch {
      /* sidebar is best-effort */
    }
  }

  useEffect(() => {
    let alive = true;
    listChatSessions()
      .then((s) => {
        if (alive) setSessions(s);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

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
      refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function loadSession(id: string) {
    setError(null);
    try {
      const detail = await getChatSession(id);
      setSessionId(id);
      // Reconstruct turns from the saved user/assistant message pairs.
      // Citations aren't persisted on the session view — history shows text.
      const rebuilt: Turn[] = [];
      for (let i = 0; i < detail.messages.length; i++) {
        const m = detail.messages[i];
        if (m.role !== "user") continue;
        const reply = detail.messages[i + 1];
        if (reply?.role !== "assistant") continue;
        rebuilt.push({
          question: m.content,
          result: {
            session_id: id,
            message_id: reply.id,
            status: "answered",
            answer: reply.content,
            citations: [],
            evidence: [],
            warnings: [],
            intent: {
              kind: "history",
              as_of: reply.as_of_date,
              compare_a: null,
              compare_b: null,
              ambiguous: false,
              resolved_by: "session_history",
            },
          },
        });
      }
      setTurns(rebuilt);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load session");
    }
  }

  function newChat() {
    setSessionId(undefined);
    setTurns([]);
    setError(null);
  }

  return (
    <div className="flex h-full">
      {/* Session history */}
      <aside className="flex w-56 shrink-0 flex-col border-r bg-muted/30">
        <div className="flex items-center justify-between px-4 pb-2 pt-6">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <History className="h-3.5 w-3.5" /> Sessions
          </p>
          <button
            onClick={newChat}
            title="New chat"
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-4">
          {sessions.length === 0 && (
            <p className="px-2 py-4 text-xs text-muted-foreground">
              No conversations yet.
            </p>
          )}
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => loadSession(s.id)}
              className={`w-full truncate rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                s.id === sessionId
                  ? "bg-primary/10 font-medium text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
              title={s.title ?? ""}
            >
              {s.title ?? "Untitled chat"}
            </button>
          ))}
        </div>
      </aside>

      {/* Conversation */}
      <div className="flex min-w-0 flex-1 flex-col p-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Ask</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Temporal questions answered only from versions valid at the
            requested time.
          </p>
        </div>

        <div className="mt-6 flex-1 space-y-6 overflow-y-auto pb-4">
          {turns.length === 0 && (
            <Card className="border-dashed">
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                Try: &ldquo;What is the current annual leave allowance?&rdquo;,
                &ldquo;What was it in February 2025?&rdquo;, or &ldquo;What
                changed between 2024 and 2026?&rdquo;
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
                      {INTENT_LABEL[t.result.intent.kind] ??
                        t.result.intent.kind}
                    </Badge>
                    {t.result.intent.as_of && (
                      <Badge variant="outline">
                        <CalendarClock className="mr-1 h-3 w-3" />
                        as of {t.result.intent.as_of}
                      </Badge>
                    )}
                    {t.result.intent.compare_a && (
                      <Badge variant="outline">
                        {t.result.intent.compare_a} vs{" "}
                        {t.result.intent.compare_b}
                      </Badge>
                    )}
                    <Badge
                      variant={
                        t.result.status === "answered"
                          ? "default"
                          : "destructive"
                      }
                    >
                      {t.result.status === "answered"
                        ? "answered"
                        : "insufficient evidence"}
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
                  <div className="prose prose-sm max-w-none text-sm leading-relaxed [&_p]:my-1.5">
                    <ReactMarkdown>{t.result.answer}</ReactMarkdown>
                  </div>
                  {t.result.citations.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-medium text-muted-foreground">
                        Sources — which versions answered this
                      </p>
                      <div className="space-y-2">
                        {t.result.citations.map((c) => (
                          <div
                            key={c.chunk_id}
                            className="rounded-md border p-2.5 text-xs"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-medium">
                                {c.document_title}
                              </span>
                              <Badge variant="secondary">
                                v{c.version_number}
                              </Badge>
                              <span className="text-muted-foreground">
                                effective {c.effective_from} →{" "}
                                {c.effective_until ?? "present"}
                              </span>
                              {c.page_number && (
                                <span className="text-muted-foreground">
                                  · p.{c.page_number}
                                </span>
                              )}
                              {c.section_title && (
                                <span className="text-muted-foreground">
                                  · {c.section_title}
                                </span>
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
                        +{" "}
                        {t.result.evidence.length - t.result.citations.length}{" "}
                        more retrieved passage(s) not cited
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
              <Label htmlFor="q" className="sr-only">
                Question
              </Label>
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
    </div>
  );
}
