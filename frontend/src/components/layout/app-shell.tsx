"use client";

import { usePathname } from "next/navigation";

import { BottomNav } from "@/components/layout/bottom-nav";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

const CHROMELESS_PREFIXES = ["/sign-in", "/sign-up"];

/** App chrome (sidebar, top bar, mobile tabs); hidden on the auth pages. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (CHROMELESS_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    return <main>{children}</main>;
  }

  return (
    <>
      <div className="flex min-h-dvh">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          {/* pb-20 reserves space for the mobile bottom tab bar */}
          <main className="flex-1 px-4 pb-20 pt-4 md:px-6 md:pb-6">{children}</main>
        </div>
      </div>
      <BottomNav />
    </>
  );
}
