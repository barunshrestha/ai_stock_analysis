import { TradeEditClient } from "@/components/options/trade-edit-client";

export const metadata = { title: "Edit option trade" };

export default async function EditOptionTradePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const tradeId = Number(id);
  if (!Number.isFinite(tradeId)) {
    return <p className="text-destructive">Invalid trade id.</p>;
  }
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <TradeEditClient id={tradeId} />
    </div>
  );
}
