import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";

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
