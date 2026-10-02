"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Lock, PanelLeftClose, PanelLeftOpen, TrendingUp } from "lucide-react";

import { NAV_ITEMS } from "@/lib/nav";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "sidebar-collapsed";

/** Desktop / tablet sidebar. Pure navigation — no settings or inputs (PRD req 7). */
export function Sidebar() {
  const pathname = usePathname();
  const { isSignedIn } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setCollapsed(window.localStorage.getItem(STORAGE_KEY) === "1");
  }, []);

  const toggle = () => {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  };

  return (
    <aside
      className={cn(
        "hidden shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 md:flex",
        collapsed ? "w-16" : "w-56 lg:w-60",
      )}
    >
      <div className="flex h-14 items-center border-b border-sidebar-border">
        {collapsed ? (
          <button
            type="button"
            onClick={toggle}
            aria-label="Expand navigation"
            title="Expand navigation"
            className="inline-flex h-full w-full items-center justify-center text-muted-foreground transition-colors hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
          >
            <PanelLeftOpen className="size-5" />
          </button>
        ) : (
          <>
            <Link
              href="/"
              title="Home"
              className="flex h-full min-w-0 flex-1 items-center px-4 transition-colors hover:bg-sidebar-accent/60"
            >
              <TrendingUp className="size-5 shrink-0 text-positive" />
            </Link>
            <button
              type="button"
              onClick={toggle}
              aria-label="Collapse navigation"
              title="Collapse navigation"
              className="mr-2 inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
            >
              <PanelLeftClose className="size-4" />
            </button>
          </>
        )}
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname.startsWith(item.matchPrefix);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.title}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                collapsed && "justify-center px-0",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
              )}
            >
              <span className="relative shrink-0">
                <item.icon className="size-4" />
                {collapsed && item.requiresAuth && isSignedIn === false && (
                  <Lock className="absolute -right-2 -top-1.5 size-3" aria-label="Sign in required" />
                )}
              </span>
              {!collapsed && item.title}
              {!collapsed && item.requiresAuth && isSignedIn === false && (
                <Lock className="ml-auto size-3.5" aria-label="Sign in required" />
              )}
            </Link>
          );
        })}
      </nav>
      {!collapsed && (
        <div className="border-t border-sidebar-border p-3 text-xs text-muted-foreground">
          Data: Yahoo Finance · AI: Ollama
        </div>
      )}
    </aside>
  );
}
