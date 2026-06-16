import { StockDetail } from "@/components/stocks/stock-detail";

interface Props {
  params: Promise<{ symbol: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { symbol } = await params;
  return { title: symbol.toUpperCase() };
}

export default async function StockDetailPage({ params }: Props) {
  const { symbol } = await params;
  return <StockDetail symbol={symbol.toUpperCase()} />;
}
