"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useRouter } from "next/navigation";

import type {
  CspScreenResult,
  OptionTrade,
  OptionTradeCreatePayload,
  OptionLeg,
  StrategyType,
  ParseImageResult,
} from "@/lib/api";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LEG_COUNTS, STRATEGY_LABELS } from "@/components/options/constants";
import { PreTradeAnalysisPanel } from "@/components/options/pretrade-analysis-panel";
import { CspScreenPanel } from "@/components/options/csp-screen-panel";
import type { PreTradeAnalysis } from "@/lib/api";

const SIDES = [
  { value: "sell_to_open", label: "Sell to open" },
  { value: "buy_to_close", label: "Buy to close" },
  { value: "buy_to_open", label: "Buy to open" },
  { value: "sell_to_close", label: "Sell to close" },
] as const;

function defaultLeg(index: number, strategy: StrategyType): OptionLeg {
  const isPut = strategy.includes("put") || strategy === "iron_condor";
  return {
    leg_index: index,
    option_type: isPut && index <= 2 ? "put" : "call",
    side: strategy.includes("long") ? "buy_to_open" : "sell_to_open",
    strike: 0,
    premium_per_contract: 0,
  };
}

function buildLegs(strategy: StrategyType): OptionLeg[] {
  const n = LEG_COUNTS[strategy];
  return Array.from({ length: n }, (_, i) => defaultLeg(i + 1, strategy));
}

function initialStateFromTrade(trade: OptionTrade) {
  return {
    strategy: trade.strategy_type,
    ticker: trade.ticker,
    legs: trade.legs.length ? trade.legs : buildLegs(trade.strategy_type),
    contracts: trade.contracts,
    executedAt: trade.executed_at.slice(0, 16),
    expirationDate: trade.expiration_date.slice(0, 10),
    netCreditDebit: String(trade.net_credit_debit),
    collateralOverride: trade.collateral_override != null ? String(trade.collateral_override) : "",
    notes: trade.notes ?? "",
    broker: trade.broker ?? "",
  };
}

export function TradeForm({
  tradeId,
  initialTrade,
}: {
  tradeId?: number;
  initialTrade?: OptionTrade;
}) {
  const isEdit = tradeId != null && initialTrade != null;
  const seeded = isEdit ? initialStateFromTrade(initialTrade) : null;

  const router = useRouter();
  const today = new Date().toISOString().slice(0, 10);
  const nowLocal = new Date().toISOString().slice(0, 16);

  const [strategy, setStrategy] = useState<StrategyType>(seeded?.strategy ?? "cash_secured_put");
  const [ticker, setTicker] = useState(seeded?.ticker ?? "");
  const [legs, setLegs] = useState<OptionLeg[]>(() => seeded?.legs ?? buildLegs("cash_secured_put"));
  const [contracts, setContracts] = useState(seeded?.contracts ?? 1);
  const [executedAt, setExecutedAt] = useState(seeded?.executedAt ?? nowLocal);
  const [expirationDate, setExpirationDate] = useState(seeded?.expirationDate ?? "");
  const [netCreditDebit, setNetCreditDebit] = useState(seeded?.netCreditDebit ?? "");
  const [collateralOverride, setCollateralOverride] = useState(seeded?.collateralOverride ?? "");
  const [notes, setNotes] = useState(seeded?.notes ?? "");
  const [broker, setBroker] = useState(seeded?.broker ?? "");
  const [preTrade, setPreTrade] = useState<PreTradeAnalysis | null>(null);
  const [cspScreen, setCspScreen] = useState<CspScreenResult | null>(null);
  const [parseInfo, setParseInfo] = useState<ParseImageResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"form" | "analyze">("form");

  const onStrategyChange = (s: StrategyType) => {
    setStrategy(s);
    setLegs(buildLegs(s));
    setCspScreen(null);
  };

  const screenMut = useMutation({
    mutationFn: () => api.cspScreen(ticker, strategy),
    onSuccess: (data) => {
      setCspScreen(data);
      setError(null);
    },
    onError: (e: Error) => setError(e instanceof ApiError ? e.message : "Stock screen failed"),
  });

  const applySuggestedContract = () => {
    const c = cspScreen?.suggested_contract;
    if (!c) return;
    if (c.expiration.includes("/")) {
      const [m, d, y] = c.expiration.split("/");
      setExpirationDate(`${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`);
    } else {
      setExpirationDate(c.expiration.slice(0, 10));
    }
    const optionType = c.option_type ?? "put";
    const side = c.side ?? "sell_to_open";
    const signedPremium = side === "buy_to_open" ? -Math.abs(c.premium_mid) : Math.abs(c.premium_mid);
    setNetCreditDebit(String(signedPremium));
    setLegs((prev) =>
      prev.map((leg, i) =>
        i === 0
          ? {
              ...leg,
              strike: c.strike,
              premium_per_contract: c.premium_mid,
              option_type: optionType,
              side,
            }
          : leg,
      ),
    );
  };

  const handleSave = () => {
    if (cspScreen?.recommendation_color === "red") {
      const ok = window.confirm(
        "Stock screen flagged elevated risk (red). Save this trade anyway?",
      );
      if (!ok) return;
    }
    saveMut.mutate();
  };

  const payload = (): OptionTradeCreatePayload => ({
    strategy_type: strategy,
    ticker: ticker.toUpperCase(),
    legs: legs.map((l) => ({ ...l, strike: Number(l.strike), premium_per_contract: Number(l.premium_per_contract) })),
    contracts: Number(contracts),
    executed_at: new Date(executedAt).toISOString(),
    expiration_date: expirationDate,
    net_credit_debit: Number(netCreditDebit),
    collateral_override: collateralOverride ? Number(collateralOverride) : null,
    broker: broker || null,
    notes: notes || null,
  });

  const analyzeMut = useMutation({
    mutationFn: () => api.optionsPreTradeAnalyze(payload()),
    onSuccess: (data) => {
      setPreTrade(data);
      setStep("analyze");
      setError(null);
    },
    onError: (e: Error) => setError(e instanceof ApiError ? e.message : "Analysis failed"),
  });

  const saveMut = useMutation({
    mutationFn: () =>
      isEdit
        ? api.optionsUpdateTrade(tradeId, payload())
        : api.optionsCreateTrade(payload()),
    onSuccess: (trade) => router.push(`/options/${trade.id}`),
    onError: (e: Error) => setError(e instanceof ApiError ? e.message : isEdit ? "Update failed" : "Save failed"),
  });

  const parseImageMut = useMutation({
    mutationFn: (file: File) => api.optionsParseImage(file, broker || undefined),
    onSuccess: (data) => {
      setParseInfo(data);
      applyDraft(data);
    },
    onError: (e: Error) => setError(e instanceof ApiError ? e.message : "Parse failed"),
  });

  const applyDraft = (data: ParseImageResult) => {
    const d = data.draft;
    if (d.strategy_type) onStrategyChange(d.strategy_type as StrategyType);
    if (d.ticker) setTicker(d.ticker);
    if (d.legs?.length) setLegs(d.legs as OptionLeg[]);
    if (d.contracts) setContracts(d.contracts);
    if (d.executed_at) setExecutedAt(d.executed_at.slice(0, 16));
    if (d.expiration_date) setExpirationDate(d.expiration_date);
    if (d.net_credit_debit != null) setNetCreditDebit(String(d.net_credit_debit));
    if (d.broker) setBroker(d.broker);
  };

  const updateLeg = (idx: number, patch: Partial<OptionLeg>) => {
    setLegs((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  };

  if (step === "analyze") {
    return (
      <div className="space-y-4">
        {cspScreen && <CspScreenPanel screen={cspScreen} onApply={applySuggestedContract} />}
        <PreTradeAnalysisPanel analysis={preTrade} />
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setStep("form")}>
            Adjust trade
          </Button>
          <Button onClick={handleSave} disabled={saveMut.isPending}>
            {saveMut.isPending ? "Saving…" : isEdit ? "Update trade" : "Save trade"}
          </Button>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    );
  }

  return (
    <Tabs defaultValue="manual" className="space-y-4">
      {!isEdit && (
        <TabsList>
          <TabsTrigger value="manual">Manual entry</TabsTrigger>
          <TabsTrigger value="upload">Upload screenshot</TabsTrigger>
        </TabsList>
      )}

      {!isEdit && (
      <TabsContent value="upload" className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">OCR from screenshot</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              type="file"
              accept="image/*"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) parseImageMut.mutate(f);
              }}
            />
            <p className="text-xs text-muted-foreground">
              Requires Tesseract OCR on the server (pytesseract + Pillow). You can edit all fields after parse.
            </p>
            {parseInfo && (
              <div className="rounded-md border bg-muted/30 p-3 text-sm">
                <p>
                  Parse confidence: {(parseInfo.parse_confidence * 100).toFixed(0)}% · Suggested:{" "}
                  {STRATEGY_LABELS[parseInfo.detected_strategy as StrategyType] ??
                    parseInfo.detected_strategy}
                </p>
                {parseInfo.uncertain_fields.length > 0 && (
                  <p className="text-amber-600 dark:text-amber-400">
                    Review: {parseInfo.uncertain_fields.join(", ")}
                  </p>
                )}
                {parseInfo.trade_type_suggestions.map((s, i) => (
                  <p key={i} className="mt-2 text-xs text-muted-foreground">
                    {s.impact}
                  </p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </TabsContent>
      )}

      {!isEdit && <TabsContent value="manual" />}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Trade details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Strategy</span>
            <select
              className="w-full rounded-md border bg-background px-3 py-2"
              value={strategy}
              onChange={(e) => onStrategyChange(e.target.value as StrategyType)}
            >
              {Object.entries(STRATEGY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Ticker</span>
            <div className="flex gap-2">
              <Input
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="AAPL"
                readOnly={isEdit}
                className={isEdit ? "bg-muted" : undefined}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => screenMut.mutate()}
                disabled={screenMut.isPending || !ticker}
              >
                {screenMut.isPending ? "Screening…" : "Screen ticker"}
              </Button>
            </div>
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Contracts</span>
            <Input type="number" min={1} value={contracts} onChange={(e) => setContracts(Number(e.target.value))} />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Net credit (+) / debit (−) per contract</span>
            <Input value={netCreditDebit} onChange={(e) => setNetCreditDebit(e.target.value)} placeholder="2.15" />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Executed at</span>
            <Input type="datetime-local" value={executedAt} onChange={(e) => setExecutedAt(e.target.value)} />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Expiration</span>
            <Input type="date" value={expirationDate} min={today} onChange={(e) => setExpirationDate(e.target.value)} />
          </label>
          <label className="space-y-1 text-sm sm:col-span-2">
            <span className="text-muted-foreground">Collateral override (optional)</span>
            <Input value={collateralOverride} onChange={(e) => setCollateralOverride(e.target.value)} placeholder="For naked/custom" />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Broker</span>
            <Input value={broker} onChange={(e) => setBroker(e.target.value)} placeholder="robinhood" />
          </label>
          <label className="space-y-1 text-sm sm:col-span-2">
            <span className="text-muted-foreground">Notes</span>
            <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
        </CardContent>
      </Card>

      {cspScreen && <CspScreenPanel screen={cspScreen} onApply={applySuggestedContract} />}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Legs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {legs.map((leg, idx) => (
            <div key={leg.leg_index} className="grid gap-3 rounded-lg border p-3 sm:grid-cols-2 lg:grid-cols-4">
              <span className="text-sm font-medium sm:col-span-2 lg:col-span-4">Leg {leg.leg_index}</span>
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">Type</span>
                <select
                  className="w-full rounded-md border bg-background px-2 py-2"
                  value={leg.option_type}
                  onChange={(e) => updateLeg(idx, { option_type: e.target.value as "put" | "call" })}
                >
                  <option value="put">Put</option>
                  <option value="call">Call</option>
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">Side</span>
                <select
                  className="w-full rounded-md border bg-background px-2 py-2"
                  value={leg.side}
                  onChange={(e) => updateLeg(idx, { side: e.target.value as OptionLeg["side"] })}
                >
                  {SIDES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">Strike</span>
                <Input type="number" step="0.5" value={leg.strike || ""} onChange={(e) => updateLeg(idx, { strike: Number(e.target.value) })} />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">Premium / leg</span>
                <Input type="number" step="0.01" value={leg.premium_per_contract || ""} onChange={(e) => updateLeg(idx, { premium_per_contract: Number(e.target.value) })} />
              </label>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button onClick={() => analyzeMut.mutate()} disabled={analyzeMut.isPending || !ticker || !expirationDate}>
          {analyzeMut.isPending ? "Analyzing…" : "Run pre-trade analysis"}
        </Button>
        <Button variant="secondary" onClick={handleSave} disabled={saveMut.isPending}>
          {isEdit ? "Update without analysis" : "Save without analysis"}
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </Tabs>
  );
}
