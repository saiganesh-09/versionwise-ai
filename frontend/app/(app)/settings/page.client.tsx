"use client";



import { useEffect, useState } from "react";
import { getPublicSettings, type PublicSettings } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const LABELS: Record<keyof PublicSettings, string> = {
  environment: "Environment",
  llm_provider: "LLM provider",
  llm_model: "LLM model",
  embedding_provider: "Embedding provider",
  embedding_model: "Embedding model",
  embedding_dimensions: "Embedding dimensions",
  object_storage_provider: "Object storage",
  chunk_size_tokens: "Chunk size (tokens)",
  chunk_overlap_tokens: "Chunk overlap (tokens)",
  retrieval_top_k: "Retrieval top-k",
  retrieval_similarity_threshold: "Similarity floor",
  max_upload_mb: "Max upload (MB)",
  access_token_expire_minutes: "Token lifetime (min)",
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<PublicSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPublicSettings().then(setSettings).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Runtime configuration (read-only) — providers and models are selected
        via environment variables, never in code.
      </p>

      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
      {!settings && !error && <Skeleton className="mt-6 h-80" />}

      {settings && (
        <Card className="mt-6 max-w-2xl">
          <CardHeader>
            <CardTitle className="text-base">Backend configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="divide-y text-sm">
              {(Object.keys(LABELS) as (keyof PublicSettings)[]).map((k) => (
                <div key={k} className="flex justify-between py-2.5">
                  <dt className="text-muted-foreground">{LABELS[k]}</dt>
                  <dd className="font-mono text-xs">{String(settings[k])}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
