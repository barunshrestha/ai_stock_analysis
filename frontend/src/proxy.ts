import { clerkMiddleware } from "@clerk/nextjs/server";

// Makes the Clerk session available to server components. Route protection itself lives in each
// private section's layout (auth.protect()), and the API enforces ownership on every request.
export default clerkMiddleware({ signInUrl: "/sign-in", signUpUrl: "/sign-up" });

export const config = {
  matcher: [
    // Skip Next.js internals and static files, unless found in search params
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
