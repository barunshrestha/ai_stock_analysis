import { Bot } from "lucide-react";

import { SectionSymbolPicker } from "@/components/search/section-symbol-picker";

export const metadata = { title: "Automation" };

export default function AutomationLandingPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <Bot className="size-12 text-muted-foreground" />
      <h1 className="text-2xl font-semibold tracking-tight">
        Trading Automation
      </h1>
      <p className="max-w-md text-sm text-muted-foreground">
        Pick a stock to scan its technicals — SMA, RSI, ATR — detect trade
        setups, and generate entry, stop-loss, and target levels across five
        timeframes.
      </p>
      <SectionSymbolPicker base="/automation" label="Choose a stock to scan…" />
    </div>
  );
}
