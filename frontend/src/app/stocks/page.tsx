import { CandlestickChart } from "lucide-react";

export const metadata = { title: "Stocks" };

export default function StocksLanding() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <CandlestickChart className="size-12 text-muted-foreground" />
      <h1 className="text-2xl font-semibold tracking-tight">Stock Analysis</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        Search for any stock using the search bar above (or press{" "}
        <kbd className="rounded border bg-muted px-1 font-mono text-xs">⌘K</kbd>
        ). Selecting a result opens its full analysis — charts, fundamentals,
        and AI insights — automatically.
      </p>
    </div>
  );
}
