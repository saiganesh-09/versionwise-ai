"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  getMe,
  login,
  logout,
  registerUser,
  setToken,
  type UserResponse,
} from "@/lib/api";
import Link from "next/link";
import { Scale } from "lucide-react";

const credentialsSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  fullName: z.string().max(200).optional(),
});
type Credentials = z.infer<typeof credentialsSchema>;

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [user, setUser] = useState<UserResponse | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Already-authenticated visitors go straight into the app.
  useEffect(() => {
    getMe()
      .then(() => router.replace("/dashboard"))
      .catch(() => {});
  }, [router]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Credentials>({ resolver: zodResolver(credentialsSchema) });

  async function onSubmit(data: Credentials) {
    setBusy(true);
    setServerError(null);
    try {
      if (mode === "register") {
        await registerUser(data.email, data.fullName ?? "", data.password);
      }
      const tokens = await login(data.email, data.password);
      setToken(tokens.access_token);
      router.replace("/dashboard");
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function onLogout() {
    try {
      await logout();
    } finally {
      setToken(null);
      setUser(null);
    }
  }

  if (user) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center bg-gradient-to-b from-slate-50 to-blue-50/40 px-6 bg-background">
        <div className="w-full max-w-md rounded-2xl border bg-card p-8 shadow-lg shadow-primary/5">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Scale className="h-5 w-5" />
          </span>
          <h1 className="mt-4 text-xl font-semibold">Signed in</h1>
          <dl className="mt-4 space-y-2 text-sm text-muted-foreground">
            <div className="flex justify-between">
              <dt>Email</dt>
              <dd className="font-mono">{user.email}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Name</dt>
              <dd className="text-foreground">{user.full_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Role</dt>
              <dd className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {user.role}
              </dd>
            </div>
          </dl>
          <Link
            href="/dashboard"
            className="mt-6 block w-full rounded-lg bg-primary px-4 py-2.5 text-center text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90"
          >
            Continue to dashboard →
          </Link>
          <button
            onClick={onLogout}
            className="mt-3 w-full rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            Sign out
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="relative flex flex-1 flex-col items-center justify-center bg-gradient-to-b from-slate-50 to-blue-50/40 px-6 bg-background">
      <div className="w-full max-w-md rounded-2xl border bg-card p-8 shadow-lg shadow-primary/5">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Scale className="h-5 w-5" />
        </span>
        <h1 className="mt-4 text-xl font-semibold tracking-tight">
          {mode === "login" ? "Welcome back" : "Create account"}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {mode === "login"
            ? "Sign in to your VersionWise workspace"
            : "Set up your VersionWise account"}
        </p>
        <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4">
          {mode === "register" && (
            <div>
              <label className="mb-1 block text-sm font-medium text-foreground dark:text-slate-300">
                Full name
              </label>
              <input
                {...register("fullName")}
                className="w-full rounded-lg border border-input px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20  bg-background"
                autoComplete="name"
              />
              {errors.fullName && (
                <p className="mt-1 text-xs text-red-600">{errors.fullName.message}</p>
              )}
            </div>
          )}
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground dark:text-slate-300">
              Email
            </label>
            <input
              {...register("email")}
              type="email"
              className="w-full rounded-lg border border-input px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20  bg-background"
              autoComplete="email"
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
            )}
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground dark:text-slate-300">
              Password
            </label>
            <input
              {...register("password")}
              type="password"
              className="w-full rounded-lg border border-input px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20  bg-background"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
            {errors.password && (
              <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
            )}
          </div>
          {serverError && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
              {serverError}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <button
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setServerError(null);
          }}
          className="mt-4 w-full text-center text-sm text-primary hover:underline dark:text-blue-400"
        >
          {mode === "login"
            ? "Need an account? Register"
            : "Have an account? Sign in"}
        </button>
      </div>
    </main>
  );
}
