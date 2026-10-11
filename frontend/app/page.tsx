import Link from "next/link";
import { BackendStatus } from "@/components/backend-status";
import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  FileSearch,
  GitBranch,
  CodeXml,
  Scale,
  ShieldCheck,
} from "lucide-react";

const FEATURES = [
  {
    icon: CalendarClock,
    title: "Time-aware answers",
    body: "Ask 'what was the policy in February 2025?' and get the version that was actually in force — not the newest upload.",
  },
  {
    icon: GitBranch,
    title: "Versioned documents",
    body: "Every revision is immutable, dated, approved, and kept — compare any two paragraph by paragraph.",
  },
  {
    icon: FileSearch,
    title: "Evidence, not vibes",
    body: "Answers cite the exact document, version, effective range, and page — and honestly say when evidence is missing.",
  },
  {
    icon: AlertTriangle,
    title: "Conflicts surfaced",
    body: "Contradictory policies across documents are detected, persisted, and routed to human review — never silently averaged.",
  },
];

const STATS = [
  { value: "105", label: "Backend tests on real Postgres" },
  { value: "5/5", label: "Eval metrics at 1.0" },
  { value: "10", label: "Tables w/ pgvector HNSW" },
  { value: "14", label: "Phases planned & shipped" },
];

const STACK = [
  "Next.js 16", "TypeScript", "Tailwind 4", "shadcn/ui",
  "FastAPI", "SQLAlchemy 2.x", "pgvector", "JWT/RBAC",
  "pytest", "Alembic", "Docker", "RustFS/S3",
];

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      {/* Top nav */}
      <header className="sticky top-0 z-10 border-b bg-white/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-3.5">
          <span className="flex items-center gap-2 text-lg font-semibold tracking-tight">
            <Scale className="h-5 w-5 text-primary" />
            VersionWise <span className="text-primary">AI</span>
          </span>
          <div className="flex items-center gap-3">
            <a
              href="https://github.com/saiganesh-09/versionwise-ai"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              <CodeXml className="h-4 w-4" /> Source
            </a>
            <Link
              href="/login"
              className="rounded-lg bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
            >
              Sign in
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(60rem 30rem at 70% -10%, oklch(0.51 0.23 264 / 0.10), transparent), radial-gradient(40rem 20rem at 10% 30%, oklch(0.65 0.15 200 / 0.08), transparent)",
          }}
        />
        <div className="mx-auto flex w-full max-w-4xl flex-col items-center px-6 pb-20 pt-24 text-center">
          <BackendStatus />
          <h1 className="mt-6 text-5xl font-bold tracking-tight sm:text-6xl">
            Document answers with a{" "}
            <span className="bg-gradient-to-r from-primary to-cyan-600 bg-clip-text text-transparent">
              memory of time
            </span>
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-muted-foreground">
            Most RAG systems answer with whatever was uploaded last. VersionWise
            AI knows <em>when</em> a rule was true — it retrieves the version
            that was actually in force on the date you ask about, cites it, and
            flags contradictions instead of hiding them.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/login"
              className="group inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow-md shadow-primary/25 transition hover:opacity-95"
            >
              Open the app
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href="https://github.com/saiganesh-09/versionwise-ai"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border bg-card px-6 py-3 text-sm font-medium shadow-sm hover:bg-muted"
            >
              <CodeXml className="h-4 w-4" /> View source
            </a>
          </div>

          {/* Credibility strip */}
          <div className="mt-14 grid w-full grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-4">
            {STATS.map((s) => (
              <div key={s.label} className="bg-card px-4 py-5">
                <p className="text-2xl font-semibold text-primary">{s.value}</p>
                <p className="mt-1 text-xs text-muted-foreground">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* The problem */}
      <section className="border-y bg-muted/40">
        <div className="mx-auto max-w-4xl px-6 py-14">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary">
            The problem
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">
            &ldquo;How many days of annual leave do employees get?&rdquo;
          </h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {[
              { q: "Policy says…", a: "12, 15, or 20 days — depending on which version your RAG grabs first." },
              { q: "Correct answer?", a: "Depends on the date you meant. All three were true at different times." },
              { q: "VersionWise?", a: "Asks 'when?', retrieves the version in force then, cites it, warns on conflicts." },
            ].map((c) => (
              <div key={c.q} className="rounded-xl border bg-card p-5 shadow-sm">
                <p className="text-sm font-semibold">{c.q}</p>
                <p className="mt-1.5 text-sm text-muted-foreground">{c.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto w-full max-w-6xl px-6 py-16">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">
          What it does
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">
          Temporal retrieval, not just retrieval
        </h2>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="group rounded-xl border bg-card p-5 shadow-sm transition hover:border-primary/40 hover:shadow-md"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary transition group-hover:bg-primary group-hover:text-primary-foreground">
                <Icon className="h-4.5 w-4.5" />
              </div>
              <h3 className="mt-4 font-semibold">{title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                {body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Stack + trust */}
      <section className="border-t bg-muted/40">
        <div className="mx-auto max-w-6xl px-6 py-12">
          <div className="flex flex-wrap items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <p className="mr-3 text-sm font-semibold">Built with</p>
            {STACK.map((t) => (
              <span
                key={t}
                className="rounded-full border bg-card px-3 py-1 text-xs text-muted-foreground"
              >
                {t}
              </span>
            ))}
          </div>
          <p className="mt-6 text-xs text-muted-foreground">
            VersionWise AI — version-aware enterprise document intelligence.
            AuthZ enforced in SQL · citations validated against retrieved
            evidence · contradictions get a human-review workflow, not a coin
            flip.
          </p>
        </div>
      </section>
    </main>
  );
}
