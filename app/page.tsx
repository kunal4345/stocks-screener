"use client";

import { useState, useEffect } from "react";

type Stock = {
  ticker: string;
  price: number;
  score: number;
  perf_1m: number;
  perf_3m?: number;
  perf_1y: number;
  reasons: string[];
};

type Pick = {
  ticker: string;
  price: number;
  score: number;
  label: string;
  perf_1m: number;
  perf_1y: number;
  pct_from_high: number;
  reasons: string[];
};

type BacktestResult = {
  ticker: string;
  return_pct: number;
  buy_hold_pct: number;
  num_trades: number;
  win_rate: number;
};

const STRATEGIES = [
  { id: "hot", name: "🔥 Hot", desc: "Analyst upgrades + momentum + Reddit buzz" },
  { id: "momentum", name: "📈 Momentum", desc: "Stocks already ripping higher" },
  { id: "value", name: "💎 Value", desc: "Buffett style — cheap & profitable" },
  { id: "garp", name: "⚖️ GARP", desc: "Lynch style — growth at reasonable price" },
  { id: "dividend", name: "💰 Dividend", desc: "Growing passive income" },
  { id: "quality", name: "🏆 Quality", desc: "Best businesses, fat margins" },
];

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? "bg-green-500" : score >= 70 ? "bg-emerald-600" : "bg-yellow-600";
  return (
    <span className={`${color} text-white text-xs font-bold px-2 py-0.5 rounded-full`}>
      {score}
    </span>
  );
}

function PerfBadge({ value, label }: { value: number; label: string }) {
  return (
    <div className="text-center">
      <div className={`text-sm font-semibold ${value >= 0 ? "text-green-400" : "text-red-400"}`}>
        {value > 0 ? "+" : ""}{value}%
      </div>
      <div className="text-[10px] text-gray-500 uppercase">{label}</div>
    </div>
  );
}

export default function Home() {
  const [picks, setPicks] = useState<Pick[]>([]);
  const [picksLoading, setPicksLoading] = useState(false);
  const [picksWarning, setPicksWarning] = useState<string | null>(null);

  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(false);
  const [strategy, setStrategy] = useState("hot");
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [btLoading, setBtLoading] = useState("");
  const [quality, setQuality] = useState<string>("good");
  const [warning, setWarning] = useState<string | null>(null);
  const [fetchedAt, setFetchedAt] = useState<string | null>(null);

  const fetchPicks = async () => {
    setPicksLoading(true);
    setPicksWarning(null);
    try {
      const res = await fetch("/api/picks");
      const data = await res.json();
      setPicks(data.picks || []);
      setPicksWarning(data.warning || null);
    } catch {
      setPicks([]);
      setPicksWarning("Failed to load recommendations.");
    }
    setPicksLoading(false);
  };

  const fetchStocks = async (strat: string) => {
    setLoading(true);
    setWarning(null);
    setBacktest(null);
    try {
      const url = strat === "hot" ? "/api/hot" : `/api/screen?strategy=${strat}`;
      const res = await fetch(url);
      const data = await res.json();
      setStocks(data.stocks || []);
      setQuality(data.quality || "error");
      setWarning(data.warning || null);
      setFetchedAt(data.fetched_at || null);
    } catch {
      setStocks([]);
      setQuality("error");
      setWarning("Failed to connect. Do NOT invest based on cached data.");
    }
    setLoading(false);
  };

  const runBacktest = async (ticker: string) => {
    setBtLoading(ticker);
    setBacktest(null);
    try {
      const res = await fetch(`/api/backtest?ticker=${ticker}`);
      setBacktest(await res.json());
    } catch { /* ignore */ }
    setBtLoading("");
  };

  useEffect(() => { fetchPicks(); }, []);
  useEffect(() => { fetchStocks(strategy); }, [strategy]);

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Header */}
      <header className="border-b border-gray-800/50 backdrop-blur-sm sticky top-0 z-10 bg-[#0a0a0f]/80">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold tracking-tight">stocks.srkunal.space</h1>
            <p className="text-xs text-gray-500">Full market scan · Live data</p>
          </div>
          {fetchedAt && quality === "good" && (
            <span className="text-[10px] text-green-500 bg-green-500/10 px-2 py-1 rounded-full">
              ● Live
            </span>
          )}
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-6 space-y-10">

        {/* === TOP PICKS === */}
        <section>
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-lg font-bold">Top Picks</h2>
            <button
              onClick={fetchPicks}
              disabled={picksLoading}
              className="text-xs text-gray-400 hover:text-white transition-colors disabled:opacity-50"
            >
              {picksLoading ? "Scoring..." : "↻ Refresh"}
            </button>
          </div>
          <p className="text-xs text-gray-600 mb-4">
            Scored on: analysts · valuation · earnings · insider buying · technicals · social
          </p>

          {picksWarning && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-sm">
              ⚠️ {picksWarning}
            </div>
          )}

          {picksLoading && (
            <div className="py-12 text-center">
              <div className="inline-block w-5 h-5 border-2 border-green-500 border-t-transparent rounded-full animate-spin mb-2" />
              <p className="text-sm text-gray-400">Analyzing stocks across 6 factors...</p>
            </div>
          )}

          {!picksLoading && picks.length > 0 && (
            <div className="grid gap-3">
              {picks.map((p) => (
                <div key={p.ticker} className="group rounded-xl border border-gray-800/60 bg-gray-900/30 p-4 hover:border-green-500/30 hover:bg-gray-900/60 transition-all">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <ScoreBadge score={p.score} />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-lg">{p.ticker}</span>
                          <span className="text-gray-400 text-sm">${p.price}</span>
                        </div>
                        <span className="text-xs text-gray-500">{p.pct_from_high}% from 52w high</span>
                      </div>
                    </div>
                    <div className="flex gap-4 shrink-0">
                      <PerfBadge value={p.perf_1m} label="1M" />
                      <PerfBadge value={p.perf_1y} label="1Y" />
                    </div>
                  </div>
                  <div className="mt-3 flex gap-1.5 flex-wrap">
                    {p.reasons.map((r, i) => (
                      <span key={i} className="text-[11px] bg-white/5 text-gray-300 px-2 py-0.5 rounded-full border border-white/5">
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {!picksLoading && picks.length === 0 && !picksWarning && (
            <div className="py-8 text-center text-gray-600 text-sm">
              No stocks scored above 60 right now. Market may be overextended.
            </div>
          )}
        </section>

        {/* === STRATEGY SCREENER === */}
        <section>
          <h2 className="text-lg font-bold mb-3">Screener</h2>

          {/* Tabs */}
          <div className="flex gap-2 overflow-x-auto pb-3 -mx-4 px-4 scrollbar-hide">
            {STRATEGIES.map((s) => (
              <button
                key={s.id}
                onClick={() => setStrategy(s.id)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                  strategy === s.id
                    ? "bg-white text-black"
                    : "bg-gray-800/60 text-gray-400 hover:bg-gray-700/60 hover:text-gray-200"
                }`}
              >
                {s.name}
              </button>
            ))}
          </div>

          <p className="text-xs text-gray-600 mb-4">
            {STRATEGIES.find((s) => s.id === strategy)?.desc}
          </p>

          {/* Warnings */}
          {warning && (
            <div className={`mb-4 p-3 rounded-lg text-sm ${
              quality === "unreliable" || quality === "error"
                ? "bg-red-500/10 border border-red-500/20 text-red-300"
                : "bg-yellow-500/10 border border-yellow-500/20 text-yellow-300"
            }`}>
              {quality === "unreliable" || quality === "error" ? "⛔" : "⚠️"} {warning}
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="py-12 text-center">
              <div className="inline-block w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mb-2" />
              <p className="text-sm text-gray-400">Scanning market...</p>
            </div>
          )}

          {/* Results */}
          {!loading && stocks.length > 0 && (
            <div className="grid gap-2">
              {stocks.map((s, i) => (
                <div key={s.ticker} className="group rounded-xl border border-gray-800/40 bg-gray-900/20 p-3 sm:p-4 hover:border-gray-700 transition-all">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs text-gray-600 w-5">{i + 1}</span>
                      <span className="font-bold">{s.ticker}</span>
                      <span className="text-gray-500 text-sm">${s.price}</span>
                    </div>
                    <div className="flex gap-3 shrink-0">
                      <PerfBadge value={s.perf_1m} label="1M" />
                      {s.perf_3m !== undefined && <PerfBadge value={s.perf_3m} label="3M" />}
                      <PerfBadge value={s.perf_1y} label="1Y" />
                    </div>
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <div className="flex gap-1.5 flex-wrap">
                      {s.reasons.map((r, j) => (
                        <span key={j} className="text-[11px] bg-white/5 text-gray-400 px-2 py-0.5 rounded-full">
                          {r}
                        </span>
                      ))}
                    </div>
                    <button
                      onClick={() => runBacktest(s.ticker)}
                      className="text-[11px] text-blue-400 hover:text-blue-300 shrink-0 opacity-0 group-hover:opacity-100 sm:opacity-100 transition-opacity"
                    >
                      {btLoading === s.ticker ? "..." : "Backtest →"}
                    </button>
                  </div>
                  {backtest && backtest.ticker === s.ticker && (
                    <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs bg-black/30 rounded-lg p-3">
                      <div>Strategy: <span className="text-green-400 font-medium">{backtest.return_pct}%</span></div>
                      <div>Buy & Hold: <span className="font-medium">{backtest.buy_hold_pct}%</span></div>
                      <div>Trades: <span className="font-medium">{backtest.num_trades}</span></div>
                      <div>Win rate: <span className="font-medium">{backtest.win_rate}%</span></div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {!loading && stocks.length === 0 && !warning && (
            <div className="py-8 text-center text-gray-600 text-sm">
              No stocks pass this filter right now.
            </div>
          )}
        </section>
      </div>

      {/* Footer */}
      <footer className="border-t border-gray-800/30 mt-12">
        <div className="max-w-5xl mx-auto px-4 py-6 text-xs text-gray-600">
          Not financial advice. Data from Finviz + Yahoo Finance + Reddit. Scores are algorithmic.
        </div>
      </footer>
    </main>
  );
}
