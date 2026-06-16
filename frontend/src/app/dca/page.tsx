import { DcaBacktest } from "@/components/dca/dca-backtest";

export const metadata = { title: "DCA" };

export default function DcaPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Dollar Cost Averaging
        </h1>
        <p className="text-sm text-muted-foreground">
          Compare a score-weighted daily investment strategy against an
          equal-weight baseline over any period.
        </p>
      </div>
      <DcaBacktest />
    </div>
  );
}
