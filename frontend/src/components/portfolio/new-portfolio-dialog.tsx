"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderPlus, Loader2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

export function NewPortfolioDialog({
  onCreated,
}: {
  onCreated?: (portfolioId: number, name: string) => void;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: () => api.createPortfolio(name.trim()),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      onCreated?.(data.id, data.name);
      setOpen(false);
      setName("");
      setError(null);
    },
    onError: (e: Error) => {
      setError(e instanceof ApiError ? e.message : "Could not create portfolio");
    },
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) {
          setName("");
          setError(null);
          createMut.reset();
        }
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <FolderPlus className="size-4" />
          New portfolio
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create portfolio</DialogTitle>
          <DialogDescription>
            Name a new list to track a separate set of stocks (e.g. Dividend, Watchlist, IRA).
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Input
            placeholder="Portfolio name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && name.trim()) createMut.mutate();
            }}
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => createMut.mutate()}
              disabled={!name.trim() || createMut.isPending}
            >
              {createMut.isPending ? (
                <>
                  <Loader2 className="mr-1 size-4 animate-spin" />
                  Creating…
                </>
              ) : (
                "Create"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
