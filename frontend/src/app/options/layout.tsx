import { ProtectedSection } from "@/components/auth/protected-section";
import { MarketContextRail } from "@/components/options/market-context-rail";

export default function OptionsLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedSection>
      <div className="flex gap-6">
        <div className="min-w-0 flex-1">{children}</div>
        <MarketContextRail />
      </div>
    </ProtectedSection>
  );
}
