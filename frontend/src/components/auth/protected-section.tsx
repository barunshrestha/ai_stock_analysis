import { auth } from "@clerk/nextjs/server";

/**
 * Server layout wrapper for signed-in-only sections. Signed-out visitors are redirected
 * to /sign-in and returned here afterwards.
 */
export async function ProtectedSection({ children }: { children: React.ReactNode }) {
  await auth.protect();
  return <>{children}</>;
}
