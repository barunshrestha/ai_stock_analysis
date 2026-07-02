import { AiAnalysis } from "@/components/ai/ai-analysis";

interface Props {
  params: Promise<{ symbol: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { symbol } = await params;
  return { title: `AI · ${symbol.toUpperCase()}` };
}

export default async function AiSymbolPage({ params }: Props) {
  const { symbol } = await params;
  return <AiAnalysis symbol={symbol.toUpperCase()} />;
}
