import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { CspScanClient } from "@/components/options/csp-scan-client";
import { Button } from "@/components/ui/button";

export const metadata = { title: "Put scanner" };

export default function CspScanPage() {
  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild>
        <Link href="/options">
          <ArrowLeft className="mr-1 size-4" />
          Back to journal
        </Link>
      </Button>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Cash secured put scanner</h1>
        <p className="text-sm text-muted-foreground">
          Scan one stock for put contracts that match your risk filters.
        </p>
      </div>
      <CspScanClient />
    </div>
  );
}
