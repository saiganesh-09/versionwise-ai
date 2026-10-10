import { BackendStatus } from "@/components/backend-status";

const features = [
  {
    title: "Time-aware answers",
    body: "Ask about any point in time — answers come from the document version that was actually in force then.",
  },
  {
    title: "Verifiable citations",
    body: "Every claim links back to a document name, version, page, and effective-date range.",
  },
  {
    title: "Conflict detection",
    body: "Contradictions across versions are flagged for review instead of silently averaged away.",
  },
];

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center bg-slate-50 px-6 py-24 text-center dark:bg-slate-950">
      <BackendStatus />
      <h1 className="mt-8 max-w-3xl text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl dark:text-slate-50">
        VersionWise AI
      </h1>
      <p className="mt-4 max-w-2xl text-lg text-slate-600 dark:text-slate-400">
        Version-aware document intelligence. Ask questions against your policies
        and get answers grounded in the version that was valid at the time —
        with citations you can verify.
      </p>
      <div className="mt-14 grid w-full max-w-4xl gap-4 sm:grid-cols-3">
        {features.map((f) => (
          <div
            key={f.title}
            className="rounded-xl border border-slate-200 bg-white p-6 text-left shadow-sm dark:border-slate-800 dark:bg-slate-900"
          >
            <h2 className="font-semibold text-slate-900 dark:text-slate-100">
              {f.title}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              {f.body}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-12 text-xs text-slate-400">
        Early development build — dashboard, documents, and chat arrive in later
        phases.
      </p>
    </main>
  );
}
