"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  api,
  type CcRiskProfile,
  type CcScanContract,
  type CcScanFilters,
  type CcScanMode,
  type CcScanResult,
} from "@/lib/api";
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

type FilterInputs = Record<keyof CcScanFilters, string>;

const DEFAULT_INPUTS: FilterInputs = {
  min_annualized_return_pct: "8",
  delta_min: "0.15",
  delta_max: "0.30",
  min_otm_pct: "2",
  max_otm_pct: "5",
  min_dte: "30",
  max_dte: "45",
  min_iv_pct: "40",
  min_open_interest: "500",
  min_downside_protection_pct: "2",
  min_score: "40",
};

const TICKER_EXPLANATION =
  "The one stock to scan. One call contract covers 100 shares. Yahoo is queried only when you choose Rescan.";

const MODE_EXPLANATION =
  "Classic keeps calls that expire before the next earnings report. If Yahoo has no earnings date, every expiration in the window stays. Pre-earnings keeps a call only when the report falls on or before expiration and the report itself is inside the days window. Switching mode fills this choice only. It does not fetch new quotes.";

const FIELDS: {
  key: keyof CcScanFilters;
  label: string;
  unit: string;
  step: string;
  explanation: string;
}[] = [
  {
    key: "min_annualized_return_pct",
    label: "Min annualized return",
    unit: "%",
    step: "0.1",
    explanation:
      "Calls whose annualized return is below this percent are dropped. Annualized return is the max profit if called, divided by the stock price times 100, then scaled by 365 divided by the days left. The balanced default is 8%.",
  },
  {
    key: "delta_min",
    label: "Min delta",
    unit: "delta",
    step: "0.01",
    explanation:
      "The lowest accepted call delta, from 0 to 1. A smaller delta is farther above the stock and more likely to expire worthless. Delta is a model estimate, not an exchange greek. It must be less than or equal to the maximum.",
  },
  {
    key: "delta_max",
    label: "Max delta",
    unit: "delta",
    step: "0.01",
    explanation:
      "The highest accepted call delta. A larger delta sits closer to the stock and is more likely to be called away.",
  },
  {
    key: "min_otm_pct",
    label: "Min strike distance",
    unit: "% above spot",
    step: "0.1",
    explanation:
      "How far above the current stock price the strike must sit. A call closer than this percent is dropped.",
  },
  {
    key: "max_otm_pct",
    label: "Max strike distance",
    unit: "% above spot",
    step: "0.1",
    explanation:
      "The farthest strike still included, as a percent above the stock. It must be at least the minimum.",
  },
  {
    key: "min_dte",
    label: "Min days to expiration",
    unit: "days",
    step: "1",
    explanation:
      "The soonest expiration included, in whole calendar days. In pre-earnings mode the earnings date's own days must also sit in this window.",
  },
  {
    key: "max_dte",
    label: "Max days to expiration",
    unit: "days",
    step: "1",
    explanation:
      "The latest expiration included, in whole calendar days. It must be at least the minimum.",
  },
  {
    key: "min_iv_pct",
    label: "Min implied volatility",
    unit: "%",
    step: "1",
    explanation:
      "Calls whose implied volatility is below this percent are dropped. Every starting profile uses 40%.",
  },
  {
    key: "min_open_interest",
    label: "Min open interest",
    unit: "contracts",
    step: "1",
    explanation:
      "Calls with fewer open contracts than this whole number are dropped. A higher number usually means an easier fill.",
  },
  {
    key: "min_downside_protection_pct",
    label: "Min downside protection",
    unit: "%",
    step: "0.1",
    explanation:
      "The bid divided by the stock price, as a percent. This is how far the stock can fall before the premium is used up. Calls under this percent are dropped.",
  },
  {
    key: "min_score",
    label: "Min composite score",
    unit: "points",
    step: "1",
    explanation:
      "Calls scoring below this 0–100 rank are hidden when a higher-scoring call is in the same scan. A single match scores 100. 30 points are liquidity, 25 are annualized return, 25 are the chance of keeping the premium, and 20 are implied volatility.",
  },
];

const RESULT_COLUMNS: { label: string; explanation: string }[] = [
  { label: "Symbol", explanation: "The stock this call is written on. One scan covers a single symbol." },
  { label: "Expiration", explanation: "The date the contract expires. Only expirations inside your day window are included." },
  { label: "Strike", explanation: "The price at which your 100 shares would be called away." },
  {
    label: "Bid",
    explanation: "The premium per share a buyer is currently bidding. This is a delayed Yahoo quote.",
  },
  {
    label: "Delta",
    explanation: "A model estimate of assignment chance, shown from 0 to 1. This is not an exchange greek.",
  },
  { label: "IV", explanation: "Implied volatility as a percent. A higher number means a richer premium." },
  { label: "Open interest", explanation: "How many of these contracts are still open." },
  { label: "DTE", explanation: "Calendar days from today until the contract expires." },
  { label: "% above spot", explanation: "How far the strike sits above the current stock price." },
  { label: "Premium", explanation: "Cash credit for one contract if you sell at the bid. That is the bid times 100." },
  {
    label: "Downside protection",
    explanation: "The bid divided by the stock price. How far the stock can fall before the premium is used up.",
  },
  {
    label: "Max profit if called",
    explanation: "The gain if the shares are called away: the strike minus the stock price, times 100, plus the premium.",
  },
  {
    label: "Ann. return",
    explanation: "Max profit if called, divided by the stock price times 100, then scaled by 365 divided by the days left.",
  },
  { label: "Breakeven", explanation: "Stock price minus the bid. Below this price the premium no longer covers the drop." },
  { label: "Earnings", explanation: "The next earnings date Yahoo reported, or blank when Yahoo has none." },
  {
    label: "Score",
    explanation:
      "A 0–100 rank against the other calls in this scan. Click a score to see liquidity, annualized return, chance of keeping the premium, and implied volatility.",
  },
];

function filtersToInputs(filters: CcScanFilters): FilterInputs {
  return {
    min_annualized_return_pct: String(filters.min_annualized_return_pct),
    delta_min: String(filters.delta_min),
    delta_max: String(filters.delta_max),
    min_otm_pct: String(filters.min_otm_pct),
    max_otm_pct: String(filters.max_otm_pct),
    min_dte: String(filters.min_dte),
    max_dte: String(filters.max_dte),
    min_iv_pct: String(filters.min_iv_pct),
    min_open_interest: String(filters.min_open_interest),
    min_downside_protection_pct: String(filters.min_downside_protection_pct),
    min_score: String(filters.min_score),
  };
}

function validate(ticker: string, inputs: FilterInputs): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!ticker.trim()) errors.ticker = "Ticker is required.";

  const annualized = Number(inputs.min_annualized_return_pct);
  if (inputs.min_annualized_return_pct.trim() === "" || Number.isNaN(annualized) || annualized < 0) {
    errors.min_annualized_return_pct = "Minimum annualized return cannot be negative.";
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

  const minOtm = Number(inputs.min_otm_pct);
  const maxOtm = Number(inputs.max_otm_pct);
  if (inputs.min_otm_pct.trim() === "" || Number.isNaN(minOtm) || minOtm < 0) {
    errors.min_otm_pct = "Strike distance cannot be negative.";
  }
  if (inputs.max_otm_pct.trim() === "" || Number.isNaN(maxOtm) || maxOtm < 0) {
    errors.max_otm_pct = "Strike distance cannot be negative.";
  } else if (!errors.min_otm_pct && maxOtm < minOtm) {
    errors.max_otm_pct = "Maximum strike distance must be at least the minimum.";
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

  const iv = Number(inputs.min_iv_pct);
  if (inputs.min_iv_pct.trim() === "" || Number.isNaN(iv) || iv < 0) {
    errors.min_iv_pct = "Minimum implied volatility cannot be negative.";
  }

  const oi = Number(inputs.min_open_interest);
  if (inputs.min_open_interest.trim() === "" || !Number.isInteger(oi) || oi < 0) {
    errors.min_open_interest = "Minimum open interest must be a whole number zero or greater.";
  }

  const downside = Number(inputs.min_downside_protection_pct);
  if (inputs.min_downside_protection_pct.trim() === "" || Number.isNaN(downside) || downside < 0) {
    errors.min_downside_protection_pct = "Minimum downside protection cannot be negative.";
  }

  const score = Number(inputs.min_score);
  if (inputs.min_score.trim() === "" || Number.isNaN(score) || score < 0 || score > 100) {
    errors.min_score = "Minimum composite score must be between 0 and 100.";
  }

  return errors;
}

function toFilters(inputs: FilterInputs): CcScanFilters {
  return {
    min_annualized_return_pct: Number(inputs.min_annualized_return_pct),
    delta_min: Number(inputs.delta_min),
    delta_max: Number(inputs.delta_max),
    min_otm_pct: Number(inputs.min_otm_pct),
    max_otm_pct: Number(inputs.max_otm_pct),
    min_dte: Number(inputs.min_dte),
    max_dte: Number(inputs.max_dte),
    min_iv_pct: Number(inputs.min_iv_pct),
    min_open_interest: Number(inputs.min_open_interest),
    min_downside_protection_pct: Number(inputs.min_downside_protection_pct),
    min_score: Number(inputs.min_score),
  };
}

function ExplainTitle({
  label,
  unit,
  explanation,
  className,
}: {
  label: string;
  unit?: string;
  explanation: string;
  className?: string;
}) {
  return (
    <Popover>
      <PopoverTrigger
        type="button"
        className={`cursor-pointer text-left underline decoration-dotted underline-offset-4 hover:text-foreground ${className ?? ""}`}
        aria-label={`${label} explanation`}
      >
        {label}
        {unit && <span className="text-xs"> ({unit})</span>}
      </PopoverTrigger>
      <PopoverContent>
        <p className="font-medium">{label}</p>
        <p className="mt-1 text-muted-foreground">{explanation}</p>
      </PopoverContent>
    </Popover>
  );
}

function ScoreCell({ row }: { row: CcScanContract }) {
  return (
    <TableCell>
      <Popover>
        <PopoverTrigger
          type="button"
          className="cursor-pointer underline decoration-dotted underline-offset-4"
          aria-label="Score breakdown"
        >
          {row.composite_score.toFixed(1)}
        </PopoverTrigger>
        <PopoverContent>
          <p className="font-medium">Score {row.composite_score.toFixed(1)}</p>
          <ul className="mt-1 space-y-1 text-muted-foreground">
            <li>Liquidity {row.liquidity_points.toFixed(1)} / 30</li>
            <li>Annualized return {row.return_points.toFixed(1)} / 25</li>
            <li>Chance of keeping premium {row.keep_points.toFixed(1)} / 25</li>
            <li className="pl-3">About {(row.probability_of_keeping_premium * 100).toFixed(1)}% from delta</li>
            <li>Implied volatility {row.iv_points.toFixed(1)} / 20</li>
          </ul>
        </PopoverContent>
      </Popover>
    </TableCell>
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

export function CcScanClient() {
  const queryClient = useQueryClient();
  const [ticker, setTicker] = useState("");
  const [mode, setMode] = useState<CcScanMode>("classic");
  const [inputs, setInputs] = useState<FilterInputs>(DEFAULT_INPUTS);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<CcScanResult | null>(null);
  const [savedQuote, setSavedQuote] = useState(false);
  const [profileId, setProfileId] = useState("");
  const [profileName, setProfileName] = useState("");
  const [profileMessage, setProfileMessage] = useState<string | null>(null);

  const recentQ = useQuery({
    queryKey: ["cc-scans"],
    queryFn: () => api.ccScans(),
  });

  const profilesQ = useQuery({
    queryKey: ["cc-profiles"],
    queryFn: () => api.ccProfiles(),
  });

  const selectedProfile = profilesQ.data?.profiles.find((profile) => String(profile.id) === profileId);

  const rememberProfile = (profile: CcRiskProfile) => {
    queryClient.setQueryData<{ profiles: CcRiskProfile[] }>(["cc-profiles"], (current) => {
      const profiles = current?.profiles.filter((item) => item.id !== profile.id) ?? [];
      return { profiles: [...profiles, profile].sort((a, b) => a.id - b.id) };
    });
    setProfileId(String(profile.id));
    setProfileName(profile.name);
    setProfileMessage(null);
  };

  const profileError = (error: unknown) => {
    setProfileMessage(error instanceof ApiError ? error.message : "Could not update profiles.");
  };

  const createProfile = useMutation({
    mutationFn: (body: { name: string; filters: CcScanFilters }) => api.createCcProfile(body.name, body.filters),
    onSuccess: rememberProfile,
    onError: profileError,
  });

  const updateProfile = useMutation({
    mutationFn: (body: { id: number; name: string }) => api.updateCcProfile(body.id, { name: body.name }),
    onSuccess: rememberProfile,
    onError: profileError,
  });

  const removeProfile = useMutation({
    mutationFn: (id: number) => api.deleteCcProfile(id),
    onSuccess: async () => {
      setProfileId("");
      setProfileName("");
      setProfileMessage(null);
      await queryClient.invalidateQueries({ queryKey: ["cc-profiles"] });
    },
    onError: profileError,
  });

  const filterErrors = () => {
    const errors = validate("OK", inputs);
    delete errors.ticker;
    setFieldErrors(errors);
    return Object.keys(errors).length > 0;
  };

  const chooseProfile = (id: string) => {
    setProfileId(id);
    const profile = profilesQ.data?.profiles.find((item) => String(item.id) === id);
    if (!profile) return;
    setInputs(filtersToInputs(profile.filters));
    setProfileName(profile.name);
    setFieldErrors({});
    setProfileMessage(null);
  };

  const saveProfile = () => {
    const name = profileName.trim();
    if (!name) {
      setProfileMessage("Enter a profile name.");
      return;
    }
    if (filterErrors()) return;
    setProfileMessage(null);
    createProfile.mutate({ name, filters: toFilters(inputs) });
  };

  const renameProfile = () => {
    if (!selectedProfile) {
      setProfileMessage("Choose a profile to rename.");
      return;
    }
    const name = profileName.trim();
    if (!name) {
      setProfileMessage("Enter a profile name.");
      return;
    }
    setProfileMessage(null);
    updateProfile.mutate({ id: selectedProfile.id, name });
  };

  const duplicateProfile = () => {
    if (!selectedProfile) {
      setProfileMessage("Choose a profile to duplicate.");
      return;
    }
    const name = window.prompt("Name for the copy", "");
    const trimmed = name?.trim() ?? "";
    if (!trimmed) {
      setProfileMessage("Enter a new name for the copy.");
      return;
    }
    if (trimmed === selectedProfile.name) {
      setProfileMessage("Enter a new name for the copy.");
      return;
    }
    setProfileMessage(null);
    createProfile.mutate({ name: trimmed, filters: selectedProfile.filters });
  };

  const scanMut = useMutation({
    mutationFn: () =>
      api.ccScan({ ticker: ticker.trim().toUpperCase(), mode, filters: toFilters(inputs) }),
    onSuccess: (data) => {
      setResult(data);
      setSavedQuote(false);
      setFieldErrors({});
      void queryClient.invalidateQueries({ queryKey: ["cc-scans"] });
    },
  });

  const rescan = () => {
    const errors = validate(ticker, inputs);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    scanMut.mutate();
  };

  const restore = (scan: CcScanResult) => {
    setTicker(scan.ticker);
    setMode(scan.mode);
    setInputs(filtersToInputs(scan.filters));
    setResult(scan);
    setSavedQuote(true);
    setFieldErrors({});
    scanMut.reset();
  };

  const setField = (key: keyof CcScanFilters, value: string) => {
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
                        disclaimer:
                          "Bids are delayed Yahoo Finance quotes. Delta is a model estimate, not an exchange greek. Not financial advice — for journaling and education only.",
                      })
                    }
                  >
                    <span className="font-medium">{scan.ticker}</span>
                    <span className="text-muted-foreground">
                      {scan.match_count} {scan.match_count === 1 ? "call" : "calls"}
                    </span>
                    <span className="text-muted-foreground">
                      {scan.mode === "pre_earnings" ? "Pre-earnings" : "Classic"}
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
          <div className="space-y-2">
            <label className="block max-w-xs space-y-1 text-sm">
              <span className="text-muted-foreground">Risk profile</span>
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm text-foreground dark:bg-input/30"
                value={profileId}
                aria-label="Risk profile"
                onChange={(e) => chooseProfile(e.target.value)}
              >
                <option value="">Choose a profile</option>
                {(profilesQ.data?.profiles ?? []).map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}
                  </option>
                ))}
              </select>
            </label>
            {profilesQ.isPending && <Skeleton className="h-9 w-48" />}
            {profilesQ.isError && (
              <p className="text-sm text-destructive">Could not load risk profiles.</p>
            )}
            <div className="flex flex-wrap items-end gap-2">
              <label className="block min-w-40 flex-1 space-y-1 text-sm">
                <span className="text-muted-foreground">Profile name</span>
                <Input
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  placeholder="My profile"
                  aria-label="Profile name"
                />
              </label>
              <Button type="button" variant="outline" size="sm" onClick={saveProfile}>
                Save as new
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={renameProfile}>
                Rename
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={duplicateProfile}>
                Duplicate
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!selectedProfile || removeProfile.isPending}
                onClick={() => selectedProfile && removeProfile.mutate(selectedProfile.id)}
              >
                Delete
              </Button>
            </div>
            {profileMessage && <p className="text-sm text-destructive">{profileMessage}</p>}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="block max-w-xs space-y-1 text-sm">
              <ExplainTitle label="Ticker" explanation={TICKER_EXPLANATION} className="text-muted-foreground" />
              <Input
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="AAPL"
                aria-label="Ticker"
                aria-invalid={Boolean(fieldErrors.ticker)}
              />
              {fieldErrors.ticker && <p className="text-xs text-destructive">{fieldErrors.ticker}</p>}
            </div>
            <div className="block max-w-xs space-y-1 text-sm">
              <ExplainTitle label="Mode" explanation={MODE_EXPLANATION} className="text-muted-foreground" />
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm text-foreground dark:bg-input/30"
                value={mode}
                aria-label="Mode"
                onChange={(e) => setMode(e.target.value as CcScanMode)}
              >
                <option value="classic">Classic</option>
                <option value="pre_earnings">Pre-earnings</option>
              </select>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FIELDS.map((field) => (
              <div key={field.key} className="space-y-1 text-sm">
                <ExplainTitle
                  label={field.label}
                  unit={field.unit}
                  explanation={field.explanation}
                  className="text-muted-foreground"
                />
                <Input
                  type="number"
                  inputMode="decimal"
                  step={field.step}
                  min={0}
                  value={inputs[field.key]}
                  aria-label={`${field.label} (${field.unit})`}
                  aria-invalid={Boolean(fieldErrors[field.key])}
                  onChange={(e) => setField(field.key, e.target.value)}
                />
                {fieldErrors[field.key] && (
                  <p className="text-xs text-destructive">{fieldErrors[field.key]}</p>
                )}
              </div>
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
                ? `Last scan ${when(result.scanned_at)}. These quotes are not live. `
                : `Scanned ${when(result.scanned_at)}. `}
              {result.mode === "pre_earnings" ? "Pre-earnings" : "Classic"}
              {result.earnings_date ? ` · earnings ${result.earnings_date}` : " · no earnings date"}.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {result.contracts.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Scan finished. No calls matched these filters.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    {RESULT_COLUMNS.map((column) => (
                      <TableHead key={column.label}>
                        <ExplainTitle label={column.label} explanation={column.explanation} />
                      </TableHead>
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
                      <TableCell>{row.downside_protection_pct.toFixed(1)}%</TableCell>
                      <TableCell>{money(row.max_profit_if_called)}</TableCell>
                      <TableCell>{row.annualized_return_pct.toFixed(1)}%</TableCell>
                      <TableCell>{money(row.breakeven)}</TableCell>
                      <TableCell>{row.earnings_date ?? "—"}</TableCell>
                      <ScoreCell row={row} />
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <p className="text-xs text-muted-foreground">{result.disclaimer}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
