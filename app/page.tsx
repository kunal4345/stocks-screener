"use client";

import { useState, useEffect } from "react";

type Stock = {
  ticker: string;
  company?: string;
  sector?: string;
  price: number;
  score: number;
  perf_1m: number;
  perf_3m?: number;
  perf_1y: number;
  reasons: string[];
};

type Pick = {
  ticker: string;
  company: string;
  sector: string;
  market_cap: string;
  pe: string;
  price: number;
  score: number;
  label: string;
  perf_1m: number;
  perf_1y: number;
  pct_from_high: number;
  reasons: string[];
};

const STRATEGIES = [
  { id: "momentum", name: "📈 Momentum", desc: "Stocks already ripping higher" },
  { id: "value", name: "💎 Value", desc: "Buffett style — cheap & profitable" },
  { id: "garp", name: "⚖️ GARP", desc: "Lynch style — growth at reasonable price" },
  { id: "dividend", name: "💰 Dividend", desc: "Growing passive income" },
  { id: "quality", name: "🏆 Quality", desc: "Best businesses, fat margins" },
];

function Skeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="rounded-xl border border-gray-800/40 bg-gray-900/20 p-4">
          <div className="flex justify-between">
            <div className="flex gap-3">
              <div className="w-10 h-5 bg-gray-800 rounded-full" />
              <div className="w-24 h-5 bg-gray-800 rounded" />
              <div className="w-16 h-5 bg-gray-800 rounded" />
            </div>
            <div className="flex gap-3">
              <div className="w-12 h-8 bg-gray-800 rounded" />
              <div className="w-12 h-8 bg-gray-800 rounded" />
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <div className="w-20 h-4 bg-gray-800 rounded-full" />
            <div className="w-28 h-4 bg-gray-800 rounded-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 70 ? "bg-green-500" : score >= 55 ? "bg-emerald-600" : "bg-yellow-600";
  return <span className={`${color} text-white text-xs font-bold px-2 py-0.5 rounded-full`}>{score}</span>;
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
  const [picksFetchedAt, setPicksFetchedAt] = useState<string | null>(null);

  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(false);
  const [strategy, setStrategy] = useState("momentum");
  const [quality, setQuality] = useState<string>("good");
  const [warning, setWarning] = useState<string | null>(null);
  const [fetchedAt, setFetchedAt] = useState<string | null>(null);

  const cache = useState<Record<string, { stocks: Stock[]; quality: string; warning: string | null; fetchedAt: string | null }>>(() => ({}))[0];

  const fetchPicks = async (force = false) => {
    if (!force && picks.length > 0) return;
    setPicksLoading(true);
    setPicksWarning(null);
    try {
      const res = await fetch("/api/picks");
      const data = await res.json();
      setPicks(data.picks || []);
      setPicksWarning(data.warning || null);
      setPicksFetchedAt(data.fetched_at || null);
    } catch {
      setPicks([]);
      setPicksWarning("Failed to load recommendations.");
    }
    setPicksLoading(false);
  };

  const fetchStocks = async (strat: string, force = false) => {
    if (!force && cache[strat]) {
      setStocks(cache[strat].stocks);
      setQuality(cache[strat].quality);
      setWarning(cache[strat].warning);
      setFetchedAt(cache[strat].fetchedAt);
      return;
    }
    setLoading(true);
    setWarning(null);
    try {
      const res = await fetch(`/api/screen?strategy=${strat}`);
      const data = await res.json();
      setStocks(data.stocks || []);
      setQuality(data.quality || "error");
      setWarning(data.warning || null);
      setFetchedAt(data.fetched_at || null);
      cache[strat] = { stocks: data.stocks || [], quality: data.quality || "error", warning: data.warning || null, fetchedAt: data.fetched_at || null };
    } catch {
      setStocks([]);
      setQuality("error");
      setWarning("Failed to connect.");
    }
    setLoading(false);
  };

  useEffect(() => { fetchPicks(); }, []);
  useEffect(() => { fetchStocks(strategy); }, [strategy]);

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white">
      <header className="border-b border-gray-800/50 backdrop-blur-sm sticky top-0 z-10 bg-[#0a0a0f]/80">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold tracking-tight">stocks.srkunal.space</h1>
            <p className="text-xs text-gray-500">Full market scan · 500+ stocks scored</p>
          </div>
          {picksFetchedAt && (
            <span className="text-[10px] text-green-500 bg-green-500/10 px-2 py-1 rounded-full">● Live</span>
          )}
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-6 space-y-10">

        {/* === TOP PICKS === */}
        <section>
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-lg font-bold">Top Picks</h2>
            <button onClick={() => fetchPicks(true)} disabled={picksLoading}
              className="text-xs text-gray-400 hover:text-white disabled:opacity-50">
              {picksLoading ? "Scoring..." : "↻ Refresh"}
            </button>
          </div>
          <p className="text-xs text-gray-600 mb-4">
            All 500+ candidates scored · analysts · valuation · earnings · insiders · technicals
            {picksFetchedAt && <span className="ml-2 text-green-600">· {new Date(picksFetchedAt).toLocaleTimeString()}</span>}
          </p>

          {picksWarning && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-sm">
              ⚠️ {picksWarning}
            </div>
          )}

          {picksLoading && <Skeleton />}

          {!picksLoading && picks.length > 0 && (
            <div className="grid gap-3">
              {picks.map((p) => (
                <div key={p.ticker} className="rounded-xl border border-gray-800/60 bg-gray-900/30 p-4 hover:border-green-500/30 transition-all">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <ScoreBadge score={p.score} />
                        <span className="font-bold text-lg">{p.ticker}</span>
                        <span className="text-gray-400">${p.price}</span>
                        {p.pe && <span className="text-xs text-gray-500">{p.pe}</span>}
                        {p.market_cap && <span className="text-xs text-gray-600">{p.market_cap}</span>}
                      </div>
                      <p className="text-sm text-gray-400 mt-0.5">{p.company}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {p.sector && <span className="text-[10px] text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">{p.sector}</span>}
                        <span className="text-[10px] text-gray-600">{p.pct_from_high}% from high</span>
                      </div>
                    </div>
                    <div className="flex gap-4 shrink-0">
                      <PerfBadge value={p.perf_1m} label="1M" />
                      <PerfBadge value={p.perf_1y} label="1Y" />
                    </div>
                  </div>
                  <div className="mt-3 flex gap-1.5 flex-wrap">
                    {p.reasons.map((r, i) => (
                      <span key={i} className={`text-[11px] px-2 py-0.5 rounded-full border ${
                        r.includes("⚠️") ? "bg-yellow-500/10 border-yellow-500/20 text-yellow-300"
                        : r.includes("Insiders") ? "bg-green-500/10 border-green-500/20 text-green-300"
                        : "bg-white/5 border-white/5 text-gray-300"
                      }`}>{r}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {!picksLoading && picks.length === 0 && !picksWarning && (
            <div className="py-8 text-center text-gray-600 text-sm">
              No stocks scored high enough right now.
            </div>
          )}
        </section>

        {/* === SCREENER === */}
        <section>
          <h2 className="text-lg font-bold mb-3">Screener</h2>
          <div className="flex gap-2 overflow-x-auto pb-3 -mx-4 px-4 scrollbar-hide">
            {STRATEGIES.map((s) => (
              <button key={s.id} onClick={() => setStrategy(s.id)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                  strategy === s.id ? "bg-white text-black" : "bg-gray-800/60 text-gray-400 hover:bg-gray-700/60"
                }`}>{s.name}</button>
            ))}
          </div>
          <p className="text-xs text-gray-600 mb-4">{STRATEGIES.find((s) => s.id === strategy)?.desc}</p>

          {warning && (
            <div className={`mb-4 p-3 rounded-lg text-sm ${
              quality === "unreliable" || quality === "error"
                ? "bg-red-500/10 border border-red-500/20 text-red-300"
                : "bg-yellow-500/10 border border-yellow-500/20 text-yellow-300"
            }`}>{quality === "unreliable" ? "⛔" : "⚠️"} {warning}</div>
          )}

          {loading && <Skeleton />}

          {!loading && stocks.length > 0 && (
            <div className="grid gap-2">
              {stocks.map((s, i) => (
                <div key={s.ticker} className="rounded-xl border border-gray-800/40 bg-gray-900/20 p-3 sm:p-4 hover:border-gray-700 transition-all">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs text-gray-600 w-5">{i + 1}</span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-bold">{s.ticker}</span>
                          <span className="text-gray-500 text-sm">${s.price}</span>
                          {s.sector && <span className="text-[10px] text-gray-600 bg-gray-800/50 px-1.5 py-0.5 rounded hidden sm:inline">{s.sector}</span>}
                        </div>
                        {s.company && <p className="text-xs text-gray-500 truncate">{s.company}</p>}
                      </div>
                    </div>
                    <div className="flex gap-3 shrink-0">
                      <PerfBadge value={s.perf_1m} label="1M" />
                      <PerfBadge value={s.perf_1y} label="1Y" />
                    </div>
                  </div>
                  <div className="mt-2 flex gap-1.5 flex-wrap">
                    {s.reasons.map((r, j) => (
                      <span key={j} className={`text-[11px] px-2 py-0.5 rounded-full ${
                        r.includes("⚠️") ? "bg-yellow-500/10 text-yellow-300" : "bg-white/5 text-gray-400"
                      }`}>{r}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {!loading && stocks.length === 0 && !warning && (
            <div className="py-8 text-center text-gray-600 text-sm">No stocks pass this filter.</div>
          )}

          {fetchedAt && quality === "good" && (
            <p className="text-xs text-green-600 mt-3">✓ Live · {new Date(fetchedAt).toLocaleTimeString()}</p>
          )}
        </section>
      </div>

      <footer className="border-t border-gray-800/30 mt-12">
        <div className="max-w-5xl mx-auto px-4 py-6 text-xs text-gray-600">
          Not financial advice. Scores are algorithmic. Data: Finviz + Yahoo Finance + Reddit.
        </div>
      </footer>
    </main>
  );
}
