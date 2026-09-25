import type { Metadata } from "next";
import { SignIn } from "@clerk/nextjs";

import { AuthPageFrame } from "@/components/auth/auth-page-frame";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <AuthPageFrame subtitle="Sign in to manage your portfolios, options journal, and AI research.">
      <SignIn />
    </AuthPageFrame>
  );
}
