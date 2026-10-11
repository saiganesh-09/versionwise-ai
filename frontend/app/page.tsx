import Link from "next/link";
import { BackendStatus } from "@/components/backend-status";
import {
  AlertTriangle,
  CalendarClock,
  FileSearch,
  GitBranch,
} from "lucide-react";

const FEATURES = [
  {
    icon: CalendarClock,
    title: "Time-aware answers",
    body: "Ask 'what was the policy in February 2025?' and get the version that was in force then — not the newest upload.",
  },
  {
    icon: GitBranch,
    title: "Versioned documents",
    body: "Every revision is immutable, dated, approved, and kept — compare any two revisions paragraph by paragraph.",
  },
  {
    icon: FileSearch,
    title: "Evidence, not vibes",
    body: "Answers cite the exact document, version, page, and effective range — and say so when evidence is missing.",
  },
  {
    icon: AlertTriangle,
    title: "Conflicts surfaced",
    body: "Contradictory policies across sources are detected, stored, and routed to human review — never silently averaged.",
  },
];

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center bg-gradient-to-b from-slate-50 to-white px-6 dark:from-slate-950 dark:to-slate-900">
      <div className="flex w-full max-w-4xl flex-col items-center pt-20 text-center">
        <BackendStatus />
        <h1 className="mt-6 text-5xl font-bold tracking-tight">
          VersionWise <span className="text-blue-700">AI</span>
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
          Enterprise document intelligence that knows <em>when</em> a rule was true.
          Upload versioned policies, ask questions for any point in time, and get
          answers grounded in the version that was actually in force.
        </p>
        <div className="mt-8 flex gap-3">
          <Link
            href="/login"
            className="rounded-lg bg-blue-700 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-800"
          >
            Sign in
          </Link>
          <a
            href="#how"
            className="rounded-lg border px-6 py-2.5 text-sm font-medium hover:bg-muted"
          >
            How it works
          </a>
        </div>
      </div>

      <div id="how" className="mt-24 grid w-full max-w-5xl gap-6 pb-24 sm:grid-cols-2">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <div
            key={title}
            className="rounded-xl border bg-card p-6 text-left shadow-sm"
          >
            <Icon className="h-6 w-6 text-blue-700" />
            <h2 className="mt-3 font-semibold">{title}</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
          </div>
        ))}
      </div>
    </main>
  );
}
