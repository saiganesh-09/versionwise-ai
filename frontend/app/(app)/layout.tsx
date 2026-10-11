import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";

// The whole (app) group is auth-gated client content — instant-navigation
// validation can't apply, so we opt out of the dev-mode insight.
export const instant = false;

export default function AppLayout({ children }: { children: React.ReactNode }) {
  // Authenticated area: the shell + pages use dynamic hooks (usePathname,
  // localStorage token, live API). Under Cache Components they render behind
  // a Suspense boundary rather than being statically prerendered.
  return (
    <Suspense fallback={null}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
