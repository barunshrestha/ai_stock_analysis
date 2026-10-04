"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  api,
  type CspRiskProfile,
  type CspScanContract,
  type CspScanFilters,
  type CspScanResult,
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

const TICKER_EXPLANATION =
  "The one stock to scan. Yahoo is queried only when you choose Rescan. Changing a filter does not fetch new quotes.";

const FIELDS: {
  key: keyof CspScanFilters;
  label: string;
  unit: string;
  step: string;
  explanation: string;
}[] = [
  {
    key: "min_bid",
    label: "Min live bid",
    unit: "$ per share",
    step: "0.01",
    explanation:
      "Puts whose delayed Yahoo bid is below this amount per share are dropped, including a bid of zero. The scan treats that bid as the credit you would collect. The default is $0.40.",
  },
  {
    key: "min_open_interest",
    label: "Min open interest",
    unit: "contracts",
    step: "1",
    explanation:
      "Puts with fewer open contracts than this whole number are dropped. A higher number usually means an easier fill. The default is 500. Open interest also feeds the score: the 20 liquidity points are full at 2,000 contracts.",
  },
  {
    key: "delta_min",
    label: "Min delta",
    unit: "delta",
    step: "0.01",
    explanation:
      "The lowest accepted put delta, shown as a positive number from 0 to 1. A smaller delta is farther below the stock and less likely to be assigned. Delta is a model estimate, not an exchange greek. The default is 0.12, and it must be less than or equal to the maximum.",
  },
  {
    key: "delta_max",
    label: "Max delta",
    unit: "delta",
    step: "0.01",
    explanation:
      "The highest accepted put delta. A larger delta sits closer to the stock price and is more likely to be assigned. The default is 0.25.",
  },
  {
    key: "min_iv_pct",
    label: "Min implied volatility",
    unit: "%",
    step: "1",
    explanation:
      "Puts whose implied volatility is below this percent are dropped. Higher implied volatility means a richer premium for selling the put. The default is 25%. The score's 20 volatility points are full at 50% or above.",
  },
  {
    key: "min_otm_pct",
    label: "Strike distance",
    unit: "% below spot",
    step: "0.1",
    explanation:
      "How far below the current stock price the strike must sit. A put closer than this percent is dropped. The default is 3%. The score's 20 distance points are full at 15% or more below the stock.",
  },
  {
    key: "min_score",
    label: "Min composite score",
    unit: "points",
    step: "1",
    explanation:
      "Puts scoring below this 0–100 rank are hidden. Up to 40 points come from annualized return, 20 from implied volatility above your minimum, 20 from open interest above your minimum, and 20 from extra distance below the stock. The default is 40.",
  },
  {
    key: "min_dte",
    label: "Min days to expiration",
    unit: "days",
    step: "1",
    explanation:
      "The soonest expiration included, in whole calendar days. Contracts that expire sooner are left out. The default is 21, and it must be less than or equal to the maximum.",
  },
  {
    key: "max_dte",
    label: "Max days to expiration",
    unit: "days",
    step: "1",
    explanation:
      "The latest expiration included, in whole calendar days. The scan stops here so Yahoo is not asked for every listed expiration. The default is 45.",
  },
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
      "Return on capital: the premium divided by capital at risk. Capital at risk is the cash set aside (strike times 100) minus the premium. It is the return if the put expires worthless.",
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
      "A 0–100 rank against the other puts in this scan, highest first. 30 points are liquidity (open interest and bid-ask tightness), 25 are annualized return, 25 are probability of profit from delta, and 20 are implied volatility. A single match scores 100. Puts under your minimum score are hidden when a higher-scoring put is in the same scan.",
  },
];

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

function ResultColumnHeader({ label, explanation }: { label: string; explanation: string }) {
  return (
    <TableHead>
      <ExplainTitle label={label} explanation={explanation} />
    </TableHead>
  );
}

function ScoreCell({ row }: { row: CspScanContract }) {
  const hasParts = typeof row.liquidity_points === "number";
  if (!hasParts) {
    return <TableCell>{row.composite_score.toFixed(1)}</TableCell>;
  }
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
            <li>Liquidity {row.liquidity_points?.toFixed(1)} / 30</li>
            <li>Premium quality {row.premium_points?.toFixed(1)} / 25</li>
            <li>Probability of profit {row.pop_points?.toFixed(1)} / 25</li>
            {typeof row.probability_of_profit === "number" && (
              <li className="pl-3">About {(row.probability_of_profit * 100).toFixed(1)}% from delta</li>
            )}
            <li>Implied volatility {row.iv_points?.toFixed(1)} / 20</li>
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

export function CspScanClient() {
  const queryClient = useQueryClient();
  const [ticker, setTicker] = useState("");
  const [inputs, setInputs] = useState<FilterInputs>(DEFAULT_INPUTS);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<CspScanResult | null>(null);
  const [savedQuote, setSavedQuote] = useState(false);
  const [profileId, setProfileId] = useState("");
  const [profileName, setProfileName] = useState("");
  const [profileMessage, setProfileMessage] = useState<string | null>(null);

  const recentQ = useQuery({
    queryKey: ["csp-scans"],
    queryFn: () => api.cspScans(),
  });

  const profilesQ = useQuery({
    queryKey: ["csp-profiles"],
    queryFn: () => api.cspProfiles(),
  });

  const selectedProfile = profilesQ.data?.profiles.find((profile) => String(profile.id) === profileId);

  const rememberProfile = (profile: CspRiskProfile) => {
    queryClient.setQueryData<{ profiles: CspRiskProfile[] }>(["csp-profiles"], (current) => {
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
    mutationFn: (body: { name: string; filters: CspScanFilters }) =>
      api.createCspProfile(body.name, body.filters),
    onSuccess: rememberProfile,
    onError: profileError,
  });

  const updateProfile = useMutation({
    mutationFn: (body: { id: number; name: string }) => api.updateCspProfile(body.id, { name: body.name }),
    onSuccess: rememberProfile,
    onError: profileError,
  });

  const removeProfile = useMutation({
    mutationFn: (id: number) => api.deleteCspProfile(id),
    onSuccess: async () => {
      setProfileId("");
      setProfileName("");
      setProfileMessage(null);
      await queryClient.invalidateQueries({ queryKey: ["csp-profiles"] });
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
    const name = profileName.trim();
    if (!name || name === selectedProfile.name) {
      setProfileMessage("Enter a new name for the copy.");
      return;
    }
    setProfileMessage(null);
    createProfile.mutate({ name, filters: selectedProfile.filters });
  };

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

          <div className="block max-w-xs space-y-1 text-sm">
            <ExplainTitle
              label="Ticker"
              explanation={TICKER_EXPLANATION}
              className="text-muted-foreground"
            />
            <Input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="AAPL"
              aria-label="Ticker"
              aria-invalid={Boolean(fieldErrors.ticker)}
            />
            {fieldErrors.ticker && <p className="text-xs text-destructive">{fieldErrors.ticker}</p>}
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
                      <ScoreCell row={row} />
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
