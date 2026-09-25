"use client";

import { Show, SignInButton } from "@clerk/nextjs";
import { LogIn } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Renders `children` (e.g. a Generate button) for signed-in users; signed-out visitors
 * get a button that opens the Clerk sign-in modal instead.
 *
 * @example
 * <SignedInAction><Button onClick={generate}>Generate</Button></SignedInAction>
 */
export function SignedInAction({
  children,
  label = "Sign in to generate",
  className,
}: {
  children: React.ReactNode;
  label?: string;
  className?: string;
}) {
  return (
    <>
      <Show when="signed-in">{children}</Show>
      <Show when="signed-out">
        <SignInButton mode="modal">
          <Button size="sm" variant="outline" className={cn(className)}>
            <LogIn className="size-4" />
            {label}
          </Button>
        </SignInButton>
      </Show>
    </>
  );
}
