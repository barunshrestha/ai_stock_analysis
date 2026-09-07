import { TradeDetailClient } from "@/components/options/trade-detail-client";

export const metadata = { title: "Option trade" };

export default async function OptionTradeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const tradeId = Number(id);
  if (!Number.isFinite(tradeId)) {
    return <p className="text-destructive">Invalid trade id.</p>;
  }
  return <TradeDetailClient id={tradeId} />;
}
