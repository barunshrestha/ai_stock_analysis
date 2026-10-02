"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, type CspScanFilters, type CspScanResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type FilterInputs = Record<keyof CspScanFilters, string>;

const DEFAULT_INPUTS: FilterInputs = {
  min_bid: "0.40",
  min_open_interest: "500",
  delta_min: "0.12",
  delta_max: "0.25",
  min_iv_pct: "25",
  min_otm_pct: "3",
  min_score: "40",
  min_dte: "21",
  max_dte: "45",
};

const FIELDS: { key: keyof CspScanFilters; label: string; unit: string; step: string }[] = [
  { key: "min_bid", label: "Min live bid", unit: "$ per share", step: "0.01" },
  { key: "min_open_interest", label: "Min open interest", unit: "contracts", step: "1" },
  { key: "delta_min", label: "Min delta", unit: "delta", step: "0.01" },
  { key: "delta_max", label: "Max delta", unit: "delta", step: "0.01" },
  { key: "min_iv_pct", label: "Min implied volatility", unit: "%", step: "1" },
  { key: "min_otm_pct", label: "Strike distance", unit: "% below spot", step: "0.1" },
  { key: "min_score", label: "Min composite score", unit: "points", step: "1" },
  { key: "min_dte", label: "Min days to expiration", unit: "days", step: "1" },
  { key: "max_dte", label: "Max days to expiration", unit: "days", step: "1" },
];

function filtersToInputs(filters: CspScanFilters): FilterInputs {
  return {
    min_bid: filters.min_bid.toFixed(2),
    min_open_interest: String(filters.min_open_interest),
    delta_min: String(filters.delta_min),
    delta_max: String(filters.delta_max),
    min_iv_pct: String(filters.min_iv_pct),
    min_otm_pct: String(filters.min_otm_pct),
    min_score: String(filters.min_score),
    min_dte: String(filters.min_dte),
    max_dte: String(filters.max_dte),
  };
}

function validate(ticker: string, inputs: FilterInputs): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!ticker.trim()) errors.ticker = "Ticker is required.";

  const bid = Number(inputs.min_bid);
  if (inputs.min_bid.trim() === "" || Number.isNaN(bid) || bid < 0) {
    errors.min_bid = "Minimum bid cannot be negative.";
  }

  const oi = Number(inputs.min_open_interest);
  if (inputs.min_open_interest.trim() === "" || !Number.isInteger(oi) || oi < 0) {
    errors.min_open_interest = "Minimum open interest must be a whole number zero or greater.";
  }

  const deltaMin = Number(inputs.delta_min);
  const deltaMax = Number(inputs.delta_max);
  if (inputs.delta_min.trim() === "" || Number.isNaN(deltaMin) || deltaMin < 0 || deltaMin > 1) {
    errors.delta_min = "Delta must be between 0 and 1.";
  }
  if (inputs.delta_max.trim() === "" || Number.isNaN(deltaMax) || deltaMax < 0 || deltaMax > 1) {
    errors.delta_max = "Delta must be between 0 and 1.";
  } else if (!errors.delta_min && deltaMin > deltaMax) {
    errors.delta_min = "Minimum delta must be less than or equal to maximum delta.";
  }

  const iv = Number(inputs.min_iv_pct);
  if (inputs.min_iv_pct.trim() === "" || Number.isNaN(iv) || iv < 0) {
    errors.min_iv_pct = "Minimum implied volatility cannot be negative.";
  }

  const otm = Number(inputs.min_otm_pct);
  if (inputs.min_otm_pct.trim() === "" || Number.isNaN(otm) || otm < 0) {
    errors.min_otm_pct = "Strike distance cannot be negative.";
  }

  const score = Number(inputs.min_score);
  if (inputs.min_score.trim() === "" || Number.isNaN(score) || score < 0 || score > 100) {
    errors.min_score = "Minimum composite score must be between 0 and 100.";
  }

  const minDte = Number(inputs.min_dte);
  const maxDte = Number(inputs.max_dte);
  if (inputs.min_dte.trim() === "" || !Number.isInteger(minDte) || minDte < 0) {
    errors.min_dte = "Minimum days to expiration must be a whole number zero or greater.";
  }
  if (inputs.max_dte.trim() === "" || !Number.isInteger(maxDte) || maxDte < 0) {
    errors.max_dte = "Maximum days to expiration must be a whole number zero or greater.";
  } else if (!errors.min_dte && maxDte < minDte) {
    errors.max_dte = "Maximum days to expiration must be at least the minimum.";
  }

  return errors;
}

function toFilters(inputs: FilterInputs): CspScanFilters {
  return {
    min_bid: Number(inputs.min_bid),
    min_open_interest: Number(inputs.min_open_interest),
    delta_min: Number(inputs.delta_min),
    delta_max: Number(inputs.delta_max),
    min_iv_pct: Number(inputs.min_iv_pct),
    min_otm_pct: Number(inputs.min_otm_pct),
    min_score: Number(inputs.min_score),
    min_dte: Number(inputs.min_dte),
    max_dte: Number(inputs.max_dte),
  };
}

const RESULT_COLUMNS: { label: string; explanation: string }[] = [
  {
    label: "Symbol",
    explanation: "The stock this put is written on. One scan covers a single symbol.",
  },
  {
    label: "Expiration",
    explanation: "The date the contract expires. Only expirations inside your min and max days are included.",
  },
  {
    label: "Strike",
    explanation:
      "The price you would buy 100 shares at if the put is assigned. Cash set aside for one contract is the strike times 100.",
  },
  {
    label: "Bid",
    explanation:
      "The premium per share a buyer is currently bidding. This is a delayed Yahoo quote, not a live exchange bid. The scan uses this bid as the credit you would collect.",
  },
  {
    label: "Delta",
    explanation:
      "A model estimate of how much the put price changes when the stock moves by $1. For a short put it is also a rough chance of finishing in the money. Shown as a positive number between 0 and 1. This is not the exchange's own delta.",
  },
  {
    label: "IV",
    explanation:
      "Implied volatility: the size of the move the option price is assuming, as a percent. A higher number means a richer premium for selling the put. This is Yahoo's figure.",
  },
  {
    label: "Open interest",
    explanation:
      "How many of these contracts are still open. A higher number usually means it is easier to get filled. Contracts under your minimum are left out.",
  },
  {
    label: "DTE",
    explanation: "Days to expiration: calendar days from today until the contract expires.",
  },
  {
    label: "% below spot",
    explanation:
      "How far the strike sits under the current stock price. A larger percent is a wider cushion before assignment.",
  },
  {
    label: "Premium",
    explanation: "Cash credit for one contract if you sell at the bid. That is the bid times 100.",
  },
  {
    label: "ROC",
    explanation:
      "Return on capital: the premium divided by the cash you must set aside (strike times 100). It is the return if the put expires worthless.",
  },
  {
    label: "Ann. return",
    explanation:
      "Return on capital scaled to a full year: ROC times 365, divided by the days left. A short-dated put can look large on this number.",
  },
  {
    label: "Breakeven",
    explanation:
      "Strike minus the bid. If you are assigned, this is the stock price where the trade breaks even after the premium you collected.",
  },
  {
    label: "Score",
    explanation:
      "A 0–100 rank used to sort the list, highest first. Up to 40 points come from annualized return, 20 from implied volatility above your minimum, 20 from open interest above your minimum, and 20 from extra distance below the stock price. Contracts under your minimum score are hidden.",
  },
];

function ResultColumnHeader({ label, explanation }: { label: string; explanation: string }) {
  return (
    <TableHead>
      <Popover>
        <PopoverTrigger
          className="cursor-pointer underline decoration-dotted underline-offset-4 hover:text-foreground"
          aria-label={`${label} explanation`}
        >
          {label}
        </PopoverTrigger>
        <PopoverContent>
          <p className="font-medium">{label}</p>
          <p className="mt-1 text-muted-foreground">{explanation}</p>
        </PopoverContent>
      </Popover>
    </TableHead>
  );
}

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

function when(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

export function CspScanClient() {
  const queryClient = useQueryClient();
  const [ticker, setTicker] = useState("");
  const [inputs, setInputs] = useState<FilterInputs>(DEFAULT_INPUTS);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<CspScanResult | null>(null);
  const [savedQuote, setSavedQuote] = useState(false);

  const recentQ = useQuery({
    queryKey: ["csp-scans"],
    queryFn: () => api.cspScans(),
  });

  const scanMut = useMutation({
    mutationFn: () => api.cspScan({ ticker: ticker.trim().toUpperCase(), ...toFilters(inputs) }),
    onSuccess: (data) => {
      setResult(data);
      setSavedQuote(false);
      setFieldErrors({});
      void queryClient.invalidateQueries({ queryKey: ["csp-scans"] });
    },
  });

  const rescan = () => {
    const errors = validate(ticker, inputs);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    scanMut.mutate();
  };

  const restore = (scan: CspScanResult) => {
    setTicker(scan.ticker);
    setInputs(filtersToInputs(scan.filters));
    setResult(scan);
    setSavedQuote(true);
    setFieldErrors({});
    scanMut.reset();
  };

  const setField = (key: keyof CspScanFilters, value: string) => {
    setInputs((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Recent scan stocks</CardTitle>
        </CardHeader>
        <CardContent>
          {recentQ.isPending && <Skeleton className="h-9 w-48" />}
          {recentQ.isError && (
            <p className="text-sm text-destructive">Could not load recent scans.</p>
          )}
          {recentQ.data && recentQ.data.scans.length === 0 && (
            <p className="text-sm text-muted-foreground">No recent scans yet.</p>
          )}
          {recentQ.data && recentQ.data.scans.length > 0 && (
            <ul className="flex flex-col gap-2">
              {recentQ.data.scans.map((scan) => (
                <li key={scan.ticker}>
                  <Button
                    type="button"
                    size="sm"
                    variant={result?.ticker === scan.ticker ? "secondary" : "outline"}
                    className="h-auto w-full justify-start gap-3 py-2"
                    onClick={() =>
                      restore({
                        ...scan,
                        disclaimer: result?.disclaimer ?? "",
                      })
                    }
                  >
                    <span className="font-medium">{scan.ticker}</span>
                    <span className="text-muted-foreground">
                      {scan.match_count} {scan.match_count === 1 ? "put" : "puts"}
                    </span>
                    <span className="text-muted-foreground">{when(scan.scanned_at)}</span>
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="block max-w-xs space-y-1 text-sm">
            <span className="text-muted-foreground">Ticker</span>
            <Input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="AAPL"
              aria-invalid={Boolean(fieldErrors.ticker)}
            />
            {fieldErrors.ticker && <p className="text-xs text-destructive">{fieldErrors.ticker}</p>}
          </label>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FIELDS.map((field) => (
              <label key={field.key} className="space-y-1 text-sm">
                <span className="text-muted-foreground">
                  {field.label} <span className="text-xs">({field.unit})</span>
                </span>
                <Input
                  type="number"
                  inputMode="decimal"
                  step={field.step}
                  min={0}
                  value={inputs[field.key]}
                  aria-invalid={Boolean(fieldErrors[field.key])}
                  onChange={(e) => setField(field.key, e.target.value)}
                />
                {fieldErrors[field.key] && (
                  <p className="text-xs text-destructive">{fieldErrors[field.key]}</p>
                )}
              </label>
            ))}
          </div>

          <Button type="button" onClick={rescan} disabled={scanMut.isPending}>
            {scanMut.isPending ? "Scanning…" : "Rescan"}
          </Button>
          {scanMut.isError && (
            <p className="text-sm text-destructive">
              {scanMut.error instanceof ApiError ? scanMut.error.message : "Scan failed"}
            </p>
          )}
        </CardContent>
      </Card>

      {scanMut.isPending && <Skeleton className="h-40 w-full" />}

      {!scanMut.isPending && !result && !scanMut.isError && (
        <p className="text-sm text-muted-foreground">Enter a ticker and choose Rescan.</p>
      )}

      {result && !scanMut.isPending && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              {result.ticker} at {money(result.spot)}
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              {savedQuote
                ? `Last scan ${when(result.scanned_at)}. These quotes are not live.`
                : `Scanned ${when(result.scanned_at)}.`}
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {result.contracts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No puts matched these filters.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    {RESULT_COLUMNS.map((column) => (
                      <ResultColumnHeader key={column.label} {...column} />
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.contracts.map((row) => (
                    <TableRow key={`${row.expiration}-${row.strike}`}>
                      <TableCell>{row.symbol}</TableCell>
                      <TableCell>{row.expiration}</TableCell>
                      <TableCell>{money(row.strike)}</TableCell>
                      <TableCell>{money(row.bid)}</TableCell>
                      <TableCell>{row.delta.toFixed(2)}</TableCell>
                      <TableCell>{row.iv_pct.toFixed(1)}%</TableCell>
                      <TableCell>{row.open_interest.toLocaleString()}</TableCell>
                      <TableCell>{row.dte}</TableCell>
                      <TableCell>{row.otm_pct.toFixed(1)}%</TableCell>
                      <TableCell>{money(row.premium_per_contract)}</TableCell>
                      <TableCell>{row.return_on_capital_pct.toFixed(2)}%</TableCell>
                      <TableCell>{row.annualized_return_pct.toFixed(1)}%</TableCell>
                      <TableCell>{money(row.breakeven)}</TableCell>
                      <TableCell>{row.composite_score.toFixed(1)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <p className="text-xs text-muted-foreground">
              Bids are delayed Yahoo Finance quotes. Delta is a model estimate, not an exchange greek.
              Not financial advice — for journaling and education only.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
