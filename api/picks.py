"""API endpoint: Top Picks — scores ALL candidates via Finviz, Yahoo only for top 40."""

import json
import re
import requests
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone

NOISE = frozenset(
    "THE AND FOR ARE BUT NOT YOU ALL CAN HER WAS ONE OUR OUT HAS ITS CEO IPO ETF WSB DD "
    "YOLO IMO FYI PSA TIL EPS ATH GDP SEC FDA FED CPI US UK EU PM AM OP IV OTM ITM DTE "
    "LMAO WTF RIP LOL CFO COO CTO NYSE EDIT TLDR FWIW IIRC TBH SMH HODL MOASS FOMO FUD "
    "NEW NOW MAY JUST BEEN WILL WHAT THIS THAT WITH FROM HAVE THEY SOME THAN VERY MUCH "
    "ALSO OVER ONLY EVEN MOST BACK INTO YEAR WHEN YOUR MAKE LIKE LONG LOOK MANY THEN "
    "THEM EACH WELL MORE MADE AFTER COULD WOULD ABOUT WHERE BEING STILL GOING EVERY "
    "THOSE SINCE THEIR OTHER WHICH THESE FIRST THINK MIGHT SHOULD REALLY PEOPLE MARKET "
    "STOCK STOCKS MONEY PRICE SHARE TRADE SELL HOLD CALL PUTS BULL BEAR AI".split()
)

MONTHS = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}


def is_earnings_upcoming(earnings_str):
    """Returns True if earnings are within next 14 days."""
    if not earnings_str or not isinstance(earnings_str, str):
        return False
    try:
        parts = earnings_str.replace("/a", "").replace("/b", "").strip().split()
        if len(parts) != 2:
            return False
        month = MONTHS.get(parts[0], 0)
        day = int(parts[1])
        if not month:
            return False
        now = datetime.now(tz=timezone.utc)
        for year in [now.year, now.year + 1]:
            try:
                d = datetime(year, month, day, tzinfo=timezone.utc)
                if 0 <= (d - now).days <= 14:
                    return True
            except ValueError:
                continue
        return False
    except Exception:
        return False


def get_all_candidates():
    """Get ALL candidates from Finviz overview (single call — has company, sector, P/E, market cap)."""
    from finvizfinance.screener.overview import Overview

    o = Overview()
    o.set_filter(filters_dict={
        "Market Cap.": "+Mid (over $2bln)",
        "Analyst Recom.": "Buy or better",
        "EPS growththis year": "Positive (>0%)",
        "Return on Equity": "Over +15%",
    })
    df = o.screener_view()
    if df is None or df.empty:
        return [], set()

    candidates = []
    for _, row in df.iterrows():
        candidates.append({
            "ticker": row["Ticker"],
            "company": row.get("Company", ""),
            "sector": row.get("Sector", ""),
            "market_cap": row.get("Market Cap", 0),
            "pe": row.get("P/E", 0),
            "roe": 0.20,  # All passed ROE >15% filter
            "debt_eq": 1.0,  # Unknown from overview, neutral
            "earnings": "",  # Unknown from overview
        })

    valid_tickers = set(c["ticker"] for c in candidates)
    return candidates, valid_tickers


def get_insider_buys():
    """Get tickers with positive insider transactions."""
    from finvizfinance.screener.overview import Overview
    o = Overview()
    o.set_filter(filters_dict={
        "Market Cap.": "+Mid (over $2bln)",
        "InsiderTransactions": "Positive (>0%)",
        "Analyst Recom.": "Buy or better",
    })
    df = o.screener_view()
    if df is None or df.empty:
        return set()
    return set(df["Ticker"].tolist())


def get_reddit_mentions(valid_tickers):
    """Reddit mentions, validated against known tickers."""
    tickers = {}
    headers = {"User-Agent": "StockScreener/1.0"}
    for sub in ["wallstreetbets", "stocks", "investing"]:
        try:
            r = requests.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=50",
                             headers=headers, timeout=5)
            if r.status_code != 200:
                continue
            for p in r.json()["data"]["children"]:
                title = p["data"]["title"]
                for m in re.findall(r'\$([A-Z]{2,5})\b', title):
                    if m in valid_tickers:
                        tickers[m] = tickers.get(m, 0) + 3
                for m in re.findall(r'\b([A-Z]{2,5})\b', title):
                    if m in valid_tickers and m not in NOISE:
                        tickers[m] = tickers.get(m, 0) + 1
        except Exception:
            continue
    return tickers


def pre_score(candidate, insider_set, reddit_mentions):
    """Score using Finviz data ONLY (no Yahoo call). Returns 0-75 pre-score."""
    score = 0

    # Analyst: 25 pts (all passed Buy+ filter)
    score += 25

    # Valuation via P/E: 20 pts
    pe = candidate["pe"]
    if isinstance(pe, (int, float)) and pe > 0:
        if pe < 15: score += 20
        elif pe < 25: score += 15
        elif pe < 40: score += 8

    # Insider buying: 20 pts (rare and meaningful)
    if candidate["ticker"] in insider_set:
        score += 20

    # Reddit: 10 pts
    reddit_count = reddit_mentions.get(candidate["ticker"], 0)
    if reddit_count >= 5: score += 10
    elif reddit_count >= 3: score += 5

    return score


def get_price_data(ticker):
    """Yahoo price data for technical scoring."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    r = requests.get(url, params={"range": "1y", "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
    if r.status_code != 200:
        return None
    data = r.json()
    if data.get("chart", {}).get("error"):
        return None
    result = data["chart"]["result"]
    if not result:
        return None
    result = result[0]
    closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
    if len(closes) < 50:
        return None

    price = closes[-1]
    high_52w = max(closes)
    sma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else sum(closes) / len(closes)
    pct_from_high = (price / high_52w - 1) * 100
    perf_1m = (price / closes[-22] - 1) * 100 if len(closes) > 22 else 0
    perf_1y = (price / closes[0] - 1) * 100

    return {
        "price": round(price, 2),
        "pct_from_high": round(pct_from_high, 1),
        "above_200": price > sma200,
        "perf_1m": round(perf_1m, 1),
        "perf_1y": round(perf_1y, 1),
    }


def technical_score(price_data):
    """Technical timing: 15 pts max."""
    if not price_data["above_200"]:
        return 0, "Below 200-day avg ⚠️"
    pct = price_data["pct_from_high"]
    if -12 <= pct <= -5:
        return 15, f"Pullback {pct}% — good entry"
    elif -5 < pct <= -2:
        return 10, "Slight dip from highs"
    elif -2 < pct <= 0:
        return 5, "Near all-time high"
    elif pct < -12:
        return 8, f"Down {pct}% — watch for reversal"
    return 5, "At highs"


def format_market_cap(mc):
    """Format market cap to readable string."""
    if not mc or not isinstance(mc, (int, float)):
        return ""
    if mc >= 1e12: return f"${mc/1e12:.1f}T"
    if mc >= 1e9: return f"${mc/1e9:.0f}B"
    if mc >= 1e6: return f"${mc/1e6:.0f}M"
    return ""


def build_picks():
    """Pre-score ALL 505 candidates with Finviz, Yahoo-call only top 40."""
    candidates, valid_tickers = get_all_candidates()
    if not candidates:
        return None, "unreliable", "Finviz returned no candidates."

    insider_set = get_insider_buys()
    reddit_mentions = get_reddit_mentions(valid_tickers)

    # Pre-score ALL candidates (no Yahoo calls — instant)
    for c in candidates:
        c["pre_score"] = pre_score(c, insider_set, reddit_mentions)

    # Sort by pre-score, take top 40 for Yahoo calls
    candidates.sort(key=lambda x: x["pre_score"], reverse=True)
    top_candidates = candidates[:40]

    # Now add technical scoring via Yahoo
    results = []
    for c in top_candidates:
        price_data = get_price_data(c["ticker"])
        if not price_data:
            continue

        tech_pts, tech_reason = technical_score(price_data)
        total_score = c["pre_score"] + tech_pts

        # Build reasons
        reasons = []
        pe = c["pe"]
        if isinstance(pe, (int, float)) and pe > 0:
            if pe < 20:
                reasons.append(f"P/E {pe:.0f} (cheap)")
            elif pe < 40:
                reasons.append(f"P/E {pe:.0f}")
            else:
                reasons.append(f"P/E {pe:.0f} ⚠️")
        if c["ticker"] in insider_set:
            reasons.append("Insiders buying")
        reddit_count = reddit_mentions.get(c["ticker"], 0)
        if reddit_count >= 3:
            reasons.append(f"Reddit ({reddit_count})")
        reasons.append(tech_reason)

        # Label
        if total_score >= 70:
            label = "🟢 Strong Buy"
        elif total_score >= 55:
            label = "🟡 Buy"
        else:
            continue  # Skip low scores

        pe_str = f"P/E {c['pe']:.0f}" if c["pe"] and isinstance(c["pe"], (int, float)) and c["pe"] > 0 else ""

        results.append({
            "ticker": c["ticker"],
            "company": c["company"],
            "sector": c["sector"],
            "market_cap": format_market_cap(c["market_cap"]),
            "pe": pe_str,
            "price": price_data["price"],
            "score": total_score,
            "label": label,
            "perf_1m": price_data["perf_1m"],
            "perf_1y": price_data["perf_1y"],
            "pct_from_high": price_data["pct_from_high"],
            "reasons": reasons,
        })

    results.sort(key=lambda x: (x["score"], x["perf_1m"]), reverse=True)

    # Sector cap: max 3 per sector
    final = []
    sector_count = {}
    for r in results:
        s = r["sector"] or "Unknown"
        sector_count[s] = sector_count.get(s, 0) + 1
        if sector_count[s] <= 3:
            final.append(r)
        if len(final) >= 10:
            break

    if not final:
        return [], "good", "No stocks scored high enough right now."

    return final, "good", None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            stocks, quality, warning = build_picks()
            status = 503 if quality == "unreliable" else 200
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "picks": stocks or [],
                "count": len(stocks) if stocks else 0,
                "quality": quality,
                "warning": warning,
                "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            }).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "picks": [], "quality": "error",
                "warning": f"Server error: {str(e)}. Do NOT invest based on this data.",
            }).encode())
