import { BrainCircuit } from "lucide-react";

import { SectionSymbolPicker } from "@/components/search/section-symbol-picker";

export const metadata = { title: "AI Analysis" };

export default function AiLandingPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <BrainCircuit className="size-12 text-muted-foreground" />
      <h1 className="text-2xl font-semibold tracking-tight">AI Analysis</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        Pick a stock to run a 15-point AI analysis — trend, support and
        resistance, entry logic, risks, and a simple trading plan — powered by
        your local Ollama model.
      </p>
      <SectionSymbolPicker base="/ai" label="Choose a stock to analyze…" />
    </div>
  );
}
