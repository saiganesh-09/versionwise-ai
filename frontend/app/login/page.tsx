"use client";

import { useState } from "react";
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

const credentialsSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  fullName: z.string().max(200).optional(),
});
type Credentials = z.infer<typeof credentialsSchema>;

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [user, setUser] = useState<UserResponse | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
      setUser(await getMe());
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
      <main className="flex flex-1 flex-col items-center justify-center bg-slate-50 px-6 dark:bg-slate-950">
        <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">
            Signed in
          </h1>
          <dl className="mt-4 space-y-2 text-sm text-slate-600 dark:text-slate-300">
            <div className="flex justify-between">
              <dt>Email</dt>
              <dd className="font-mono">{user.email}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Name</dt>
              <dd>{user.full_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Role</dt>
              <dd className="rounded bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-800">
                {user.role}
              </dd>
            </div>
          </dl>
          <button
            onClick={onLogout}
            className="mt-6 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900"
          >
            Sign out
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center bg-slate-50 px-6 dark:bg-slate-950">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <Link href="/" className="text-xs text-slate-400 hover:text-slate-600">
          ← VersionWise AI
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-slate-900 dark:text-slate-50">
          {mode === "login" ? "Sign in" : "Create account"}
        </h1>
        <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4">
          {mode === "register" && (
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Full name
              </label>
              <input
                {...register("fullName")}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950"
                autoComplete="name"
              />
              {errors.fullName && (
                <p className="mt-1 text-xs text-red-600">{errors.fullName.message}</p>
              )}
            </div>
          )}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Email
            </label>
            <input
              {...register("email")}
              type="email"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950"
              autoComplete="email"
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
            )}
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Password
            </label>
            <input
              {...register("password")}
              type="password"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950"
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
            className="w-full rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
          >
            {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <button
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setServerError(null);
          }}
          className="mt-4 w-full text-center text-sm text-blue-700 hover:underline dark:text-blue-400"
        >
          {mode === "login"
            ? "Need an account? Register"
            : "Have an account? Sign in"}
        </button>
      </div>
    </main>
  );
}
