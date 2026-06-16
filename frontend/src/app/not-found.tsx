import Link from "next/link";
import { SearchX } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <SearchX className="size-10 text-muted-foreground" />
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        The page you&apos;re looking for doesn&apos;t exist. Use the search bar
        above to find a stock, or head back to the dashboard.
      </p>
      <Button asChild variant="outline">
        <Link href="/stocks">Go to Stocks</Link>
      </Button>
    </div>
  );
}
