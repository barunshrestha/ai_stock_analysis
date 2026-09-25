"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Lock } from "lucide-react";

import { NAV_ITEMS } from "@/lib/nav";
import { cn } from "@/lib/utils";

/** Phone-only bottom tab bar (PRD section 8). */
export function BottomNav() {
  const pathname = usePathname();
  const items = NAV_ITEMS.filter((i) => i.mobile).slice(0, 5);
  const { isSignedIn } = useAuth();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 flex h-16 items-stretch justify-around border-t bg-background/95 backdrop-blur md:hidden">
      {items.map((item) => {
        const active = pathname.startsWith(item.matchPrefix);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium",
              active ? "text-foreground" : "text-muted-foreground",
            )}
          >
            <span className="relative">
              <item.icon className={cn("size-5", active && "text-positive")} />
              {item.requiresAuth && isSignedIn === false && (
                <Lock className="absolute -right-2 -top-1 size-3" aria-label="Sign in required" />
              )}
            </span>
            {item.title}
          </Link>
        );
      })}
    </nav>
  );
}
