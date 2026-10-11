"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  FileText,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Scale,
  Settings,
} from "lucide-react";
import { getMe, logout, setToken, type UserResponse } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/chat", label: "Ask", icon: MessageSquare },
  { href: "/conflicts", label: "Conflicts", icon: AlertTriangle },
  { href: "/settings", label: "Settings", icon: Settings },
];

const ROLE_LABEL: Record<string, string> = {
  admin: "Admin",
  document_manager: "Doc manager",
  user: "Member",
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [checking, setChecking] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => {
        setToken(null);
        router.replace("/login");
      })
      .finally(() => setChecking(false));
  }, [router]);

  if (checking || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Scale className="h-4 w-4 animate-pulse text-primary" />
          Loading workspace…
        </div>
      </div>
    );
  }

  async function onLogout() {
    try {
      await logout();
    } finally {
      setToken(null);
      router.replace("/login");
    }
  }

  const initials = (user.full_name || user.email)
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col border-r bg-white/60 backdrop-blur-sm dark:bg-slate-950/60">
        <div className="px-5 py-5">
          <Link href="/dashboard" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Scale className="h-4 w-4" />
            </span>
            <span className="text-lg font-semibold tracking-tight">
              VersionWise <span className="text-primary">AI</span>
            </span>
          </Link>
          <p className="mt-1 pl-10 text-[11px] text-muted-foreground">
            Version-aware document intelligence
          </p>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <Icon className={`h-4 w-4 ${active ? "text-primary" : ""}`} />
                {label}
                {active && (
                  <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />
                )}
              </Link>
            );
          })}
        </nav>
        <div className="m-3 rounded-lg border bg-card p-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              {initials}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold">{user.full_name}</p>
              <p className="truncate text-[11px] text-muted-foreground">
                {ROLE_LABEL[user.role] ?? user.role}
              </p>
            </div>
            <button
              onClick={onLogout}
              title="Sign out"
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto bg-background">{children}</main>
    </div>
  );
}
