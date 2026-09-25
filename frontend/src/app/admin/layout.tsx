import { ProtectedSection } from "@/components/auth/protected-section";

export default function Layout({ children }: { children: React.ReactNode }) {
  return <ProtectedSection>{children}</ProtectedSection>;
}
