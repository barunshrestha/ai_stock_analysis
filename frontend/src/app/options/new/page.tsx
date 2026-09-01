import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { TradeForm } from "@/components/options/trade-form";
import { Button } from "@/components/ui/button";

export const metadata = { title: "New option trade" };

export default function NewOptionTradePage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Button variant="ghost" size="sm" asChild>
        <Link href="/options">
          <ArrowLeft className="mr-1 size-4" />
          Back to journal
        </Link>
      </Button>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">New trade</h1>
        <p className="text-sm text-muted-foreground">
          Enter manually or upload a broker screenshot, then run pre-trade analysis.
        </p>
      </div>
      <TradeForm />
    </div>
  );
}
