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
  { id: "momentum", name: "Momentum", desc: "Riding the wave — stocks already ripping higher" },
  { id: "value", name: "Value", desc: "Warren Buffett style — cheap, profitable, low debt" },
  { id: "garp", name: "GARP", desc: "Peter Lynch style — growing fast but not overpriced" },
  { id: "dividend", name: "Dividend", desc: "Passive income — growing dividends you can live off" },
  { id: "quality", name: "Quality", desc: "Best businesses — fat margins, analysts love them" },
];

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
    <main className="min-h-screen bg-black text-white p-6 max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold mb-1">stocks.srkunal.space</h1>
      <p className="text-gray-400 mb-6 text-sm">
        AI-scored stock recommendations · Full market scan
      </p>

      {/* === TOP PICKS SECTION === */}
      <section className="mb-10">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xl font-bold">Top Picks</h2>
          <button onClick={fetchPicks} className="text-xs text-gray-400 hover:text-white">
            {picksLoading ? "Loading..." : "Refresh"}
          </button>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          Composite score: analyst ratings (25%) + valuation (20%) + earnings (15%) + insider buying (15%) + technical timing (15%) + Reddit (10%)
        </p>

        {picksWarning && (
          <div className="mb-3 p-3 rounded border bg-yellow-950 border-yellow-700 text-yellow-200 text-sm">
            {picksWarning}
          </div>
        )}

        {picksLoading && <p className="text-gray-400 py-6 text-center">Scoring stocks across 6 factors...</p>}

        {!picksLoading && picks.length > 0 && (
          <div className="space-y-2">
            {picks.map((p) => (
              <div key={p.ticker} className="border border-gray-800 rounded-lg p-4 hover:border-green-800 bg-gray-950">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-sm">{p.label}</span>
                    <span className="text-xl font-bold">{p.ticker}</span>
                    <span className="text-gray-400">${p.price}</span>
                    <span className="text-sm font-mono bg-gray-800 px-2 py-0.5 rounded">
                      {p.score}/100
                    </span>
                  </div>
                  <div className="flex gap-3 text-sm">
                    <span className={p.perf_1m >= 0 ? "text-green-400" : "text-red-400"}>
                      1M: {p.perf_1m > 0 ? "+" : ""}{p.perf_1m}%
                    </span>
                    <span className="text-gray-400">
                      {p.pct_from_high}% from high
                    </span>
                  </div>
                </div>
                <div className="mt-2 flex gap-2 flex-wrap">
                  {p.reasons.map((r, i) => (
                    <span key={i} className="text-xs bg-green-950 text-green-300 border border-green-900 px-2 py-0.5 rounded">
                      {r}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {!picksLoading && picks.length === 0 && !picksWarning && (
          <p className="text-gray-500 text-center py-4">No stocks scored above 60 right now.</p>
        )}
      </section>

      {/* === STRATEGY SCREENER SECTION === */}
      <section>
        <h2 className="text-xl font-bold mb-3">Strategy Screener</h2>

        <div className="flex gap-1 mb-4 overflow-x-auto pb-2">
          {STRATEGIES.map((s) => (
            <button
              key={s.id}
              onClick={() => setStrategy(s.id)}
              className={`px-3 py-2 rounded text-sm whitespace-nowrap transition-colors ${
                strategy === s.id
                  ? "bg-green-600 text-white"
                  : "bg-gray-800 text-gray-300 hover:bg-gray-700"
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>

        <p className="text-xs text-gray-500 mb-4">
          {STRATEGIES.find((s) => s.id === strategy)?.desc}
        </p>

        {warning && (
          <div className={`mb-4 p-4 rounded-lg border ${
            quality === "unreliable" || quality === "error"
              ? "bg-red-950 border-red-700 text-red-200"
              : "bg-yellow-950 border-yellow-700 text-yellow-200"
          }`}>
            <p className="font-bold">{quality === "unreliable" || quality === "error" ? "⛔ DATA UNRELIABLE" : "⚠️ Warning"}</p>
            <p className="text-sm mt-1">{warning}</p>
          </div>
        )}

        {fetchedAt && quality === "good" && (
          <p className="text-xs text-green-600 mb-4">✓ Live data · {new Date(fetchedAt).toLocaleString()}</p>
        )}

        {loading && (
          <div className="text-gray-400 py-8 text-center">
            <p>Scanning entire market...</p>
            <p className="text-sm mt-1">~10 seconds</p>
          </div>
        )}

        {!loading && stocks.length > 0 && (
          <div className="space-y-2">
            {stocks.map((s, i) => (
              <div key={s.ticker} className="border border-gray-800 rounded-lg p-4 hover:border-gray-600">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-gray-500 text-sm mr-2">#{i + 1}</span>
                    <span className="text-xl font-bold">{s.ticker}</span>
                    <span className="ml-3 text-gray-400">${s.price}</span>
                  </div>
                  <div className="flex gap-3 text-sm">
                    <span className={s.perf_1m >= 0 ? "text-green-400" : "text-red-400"}>
                      1M: {s.perf_1m > 0 ? "+" : ""}{s.perf_1m}%
                    </span>
                    {s.perf_3m !== undefined && (
                      <span className={s.perf_3m >= 0 ? "text-green-400" : "text-red-400"}>
                        3M: {s.perf_3m > 0 ? "+" : ""}{s.perf_3m}%
                      </span>
                    )}
                    <span className={s.perf_1y >= 0 ? "text-green-400" : "text-red-400"}>
                      1Y: {s.perf_1y > 0 ? "+" : ""}{s.perf_1y}%
                    </span>
                  </div>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <div className="flex gap-2 flex-wrap">
                    {s.reasons.map((r, j) => (
                      <span key={j} className="text-xs bg-gray-800 px-2 py-1 rounded">{r}</span>
                    ))}
                  </div>
                  <button
                    onClick={() => runBacktest(s.ticker)}
                    className="text-xs text-blue-400 hover:text-blue-300"
                  >
                    {btLoading === s.ticker ? "..." : "Backtest"}
                  </button>
                </div>
                {backtest && backtest.ticker === s.ticker && (
                  <div className="mt-3 text-sm bg-gray-900 rounded p-3 grid grid-cols-4 gap-2">
                    <div>Return: <span className="text-green-400">{backtest.return_pct}%</span></div>
                    <div>B&H: {backtest.buy_hold_pct}%</div>
                    <div>Trades: {backtest.num_trades}</div>
                    <div>Win: {backtest.win_rate}%</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {!loading && stocks.length === 0 && !warning && (
          <p className="text-gray-500 py-8 text-center">No stocks pass this filter right now.</p>
        )}
      </section>

      <footer className="mt-12 text-xs text-gray-600">
        Not financial advice. Full market scan via Finviz + Yahoo Finance + Reddit. Scores are algorithmic, not human analysis.
      </footer>
    </main>
  );
}
