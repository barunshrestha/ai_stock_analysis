import type { Metadata } from "next";
import { SignUp } from "@clerk/nextjs";

import { AuthPageFrame } from "@/components/auth/auth-page-frame";

export const metadata: Metadata = { title: "Create account" };

export default function SignUpPage() {
  return (
    <AuthPageFrame subtitle="Create a free account. Your portfolios and trades stay private to you.">
      <SignUp />
    </AuthPageFrame>
  );
}
