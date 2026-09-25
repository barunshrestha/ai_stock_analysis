import Link from "next/link";
import { ClerkFailed, ClerkLoading } from "@clerk/nextjs";
import { Loader2, TrendingUp } from "lucide-react";

/** Centered, chrome-free frame for the Clerk sign-in / sign-up cards, with loading and error states. */
export function AuthPageFrame({
  subtitle,
  children,
}: {
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 px-4 py-10">
      <Link href="/" className="flex items-center gap-2">
        <TrendingUp className="size-6 text-positive" />
        <span className="text-lg font-semibold tracking-tight">Stock Analysis</span>
      </Link>
      <p className="max-w-sm text-center text-sm text-muted-foreground">{subtitle}</p>
      <ClerkLoading>
        <div className="flex h-96 w-full max-w-sm items-center justify-center rounded-xl border">
          <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Loading sign-in" />
        </div>
      </ClerkLoading>
      <ClerkFailed>
        <p className="max-w-sm text-center text-sm text-negative">
          Sign-in could not load. Check your connection and refresh the page.
        </p>
      </ClerkFailed>
      {children}
      <Link href="/stocks" className="text-sm text-muted-foreground hover:text-foreground">
        Continue browsing stocks without an account
      </Link>
    </div>
  );
}
