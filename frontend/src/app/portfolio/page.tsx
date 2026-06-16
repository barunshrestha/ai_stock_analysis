import { PortfolioGrid } from "@/components/portfolio/portfolio-grid";

export const metadata = { title: "Portfolio" };

export default function PortfolioPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">My Portfolio</h1>
        <p className="text-sm text-muted-foreground">
          Saved stocks with live metrics. Click a column to sort, a symbol to
          open its analysis.
        </p>
      </div>
      <PortfolioGrid />
    </div>
  );
}
