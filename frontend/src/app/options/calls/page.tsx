import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { CcScanClient } from "@/components/options/cc-scan-client";
import { Button } from "@/components/ui/button";

export const metadata = { title: "Covered call screener" };

export default function CoveredCallPage() {
  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild>
        <Link href="/options">
          <ArrowLeft className="mr-1 size-4" />
          Back to journal
        </Link>
      </Button>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Covered call screener</h1>
        <p className="text-sm text-muted-foreground">
          Scan one stock for a covered call on 100 shares.
        </p>
      </div>
      <CcScanClient />
    </div>
  );
}
