"use client";

import Link from "next/link";
import { ClerkLoading, Show, SignInButton, UserButton } from "@clerk/nextjs";
import { TrendingUp } from "lucide-react";

import { GlobalSearch } from "@/components/search/global-search";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/** Persistent top bar: brand (mobile), global search, theme toggle, account menu. */
export function Topbar() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur">
      <Link href="/" className="flex items-center gap-2 md:hidden">
        <TrendingUp className="size-5 text-positive" />
        <span className="font-semibold tracking-tight">Stock Analysis</span>
      </Link>
      <div className="flex flex-1 justify-center md:justify-start">
        <GlobalSearch />
      </div>
      <ThemeToggle />
      <ClerkLoading>
        <Skeleton className="size-7 rounded-full" />
      </ClerkLoading>
      <Show when="signed-in">
        <UserButton />
      </Show>
      <Show when="signed-out">
        <SignInButton mode="redirect">
          <Button size="sm">Sign in</Button>
        </SignInButton>
      </Show>
    </header>
  );
}
