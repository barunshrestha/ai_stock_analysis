import { AutomationScan } from "@/components/automation/automation-scan";

interface Props {
  params: Promise<{ symbol: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { symbol } = await params;
  return { title: `Automation · ${symbol.toUpperCase()}` };
}

export default async function AutomationSymbolPage({ params }: Props) {
  const { symbol } = await params;
  return <AutomationScan symbol={symbol.toUpperCase()} />;
}
