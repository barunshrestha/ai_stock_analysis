import { MarketContextRail } from "@/components/options/market-context-rail";

export default function OptionsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-6">
      <div className="min-w-0 flex-1">{children}</div>
      <MarketContextRail />
    </div>
  );
}
