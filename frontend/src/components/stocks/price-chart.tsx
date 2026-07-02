"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineStyle,
  createChart,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";

import { api, type Candle } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const PERIODS = [
  { label: "1M", value: "1mo" },
  { label: "3M", value: "3mo" },
  { label: "6M", value: "6mo" },
  { label: "1Y", value: "1y" },
  { label: "2Y", value: "2y" },
  { label: "5Y", value: "5y" },
] as const;

const UP = "#22c55e";
const DOWN = "#ef4444";

function toTimestamp(date: string): UTCTimestamp {
  return (new Date(date).getTime() / 1000) as UTCTimestamp;
}

export interface PriceLine {
  price: number;
  title: string;
  color: string;
}

function ChartCanvas({
  candles,
  dark,
  priceLines = [],
}: {
  candles: Candle[];
  dark: boolean;
  priceLines?: PriceLine[];
}) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const chartRef = React.useRef<IChartApi | null>(null);

  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: dark ? "#a3a3a3" : "#525252",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: dark ? "#262626" : "#f0f0f0" },
        horzLines: { color: dark ? "#262626" : "#f0f0f0" },
      },
      timeScale: { borderVisible: false },
      rightPriceScale: { borderVisible: false },
      crosshair: { mode: 0 },
    });
    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      borderUpColor: UP,
      borderDownColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
    });
    candleSeries.setData(
      candles
        .filter((c) => c.open != null && c.close != null)
        .map((c) => ({
          time: toTimestamp(c.date),
          open: c.open!,
          high: c.high ?? Math.max(c.open!, c.close!),
          low: c.low ?? Math.min(c.open!, c.close!),
          close: c.close!,
        })),
    );

    for (const line of priceLines) {
      candleSeries.createPriceLine({
        price: line.price,
        title: line.title,
        color: line.color,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
      });
    }

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    volumeSeries.setData(
      candles
        .filter((c) => c.volume != null)
        .map((c) => ({
          time: toTimestamp(c.date),
          value: c.volume!,
          color:
            (c.close ?? 0) >= (c.open ?? 0)
              ? "rgba(34,197,94,0.4)"
              : "rgba(239,68,68,0.4)",
        })),
    );

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, dark, priceLines]);

  return <div ref={containerRef} className="h-72 w-full sm:h-96" />;
}

export function PriceChart({
  symbol,
  defaultPeriod = "1y",
  priceLines,
}: {
  symbol: string;
  defaultPeriod?: string;
  priceLines?: PriceLine[];
}) {
  const [period, setPeriod] = React.useState<string>(defaultPeriod);
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const { data, isPending, isError, error } = useQuery({
    queryKey: ["history", symbol, period],
    queryFn: () => api.stockHistory(symbol, period),
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1">
        {PERIODS.map((p) => (
          <Button
            key={p.value}
            size="sm"
            variant={period === p.value ? "secondary" : "ghost"}
            className={cn("h-7 px-2.5 text-xs", period === p.value && "font-semibold")}
            onClick={() => setPeriod(p.value)}
          >
            {p.label}
          </Button>
        ))}
      </div>
      {isPending || !mounted ? (
        <Skeleton className="h-72 w-full sm:h-96" />
      ) : isError ? (
        <div className="flex h-72 items-center justify-center text-sm text-muted-foreground sm:h-96">
          Failed to load chart: {error instanceof Error ? error.message : "unknown error"}
        </div>
      ) : (
        <ChartCanvas
          candles={data.candles}
          dark={resolvedTheme === "dark"}
          priceLines={priceLines}
        />
      )}
    </div>
  );
}
