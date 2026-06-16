"use client";

import { useMutation } from "@tanstack/react-query";
import { BrainCircuit, Loader2, RefreshCw } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * On-demand Ollama summary. Generated only when requested because local LLM
 * inference takes several seconds and Ollama may not be running.
 */
export function AiSummary({ symbol }: { symbol: string }) {
  const mutation = useMutation({
    mutationFn: () => api.aiSummary(symbol),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 text-base">
          <BrainCircuit className="size-4" />
          AI Summary
        </CardTitle>
        <Button
          size="sm"
          variant={mutation.data ? "ghost" : "default"}
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Generating…
            </>
          ) : mutation.data ? (
            <>
              <RefreshCw className="size-4" />
              Regenerate
            </>
          ) : (
            "Generate"
          )}
        </Button>
      </CardHeader>
      <CardContent>
        {mutation.isIdle && (
          <p className="text-sm text-muted-foreground">
            Generate a plain-English summary of this stock&apos;s metrics using
            your local Ollama model.
          </p>
        )}
        {mutation.isPending && (
          <p className="text-sm text-muted-foreground">
            Running local model — this can take 10–30 seconds…
          </p>
        )}
        {mutation.isError && (
          <p className="text-sm text-negative">
            {mutation.error instanceof ApiError && mutation.error.status === 503
              ? "Ollama is not running. Start it with `ollama serve` and try again."
              : mutation.error instanceof Error
                ? mutation.error.message
                : "Failed to generate summary."}
          </p>
        )}
        {mutation.data && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            {mutation.data.summary}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
