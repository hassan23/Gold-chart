#!/usr/bin/env python3
"""Extend data/XAUUSD_1m.csv with new 1-minute XAU/USD candles.
- Massive (MASSIVE_KEY): clean candles through yesterday (free plan = end of day).
- Twelve Data (TWELVEDATA_KEY, optional): today's candles so the file is current; replaced by Massive tomorrow.
A 6th column "src" records where each row came from (mx = Massive, td = Twelve Data).
- Fetches every minute after the last one in the CSV, up to now (one request covers up to ~34 days).
- Timestamps are converted to New York wall-clock to match the CSV. Weekend prints are dropped.
- Free plan: 5 requests/minute; this uses 1-2 per run.
"""
import csv, json, os, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "data" / "XAUUSD_1m.csv"
NY = ZoneInfo("America/New_York"); KEY = os.environ.get("MASSIVE_KEY", "").strip(); TD = os.environ.get("TWELVEDATA_KEY", "").strip()

def load_csv():
    rows = {}
    with CSV.open() as f:
        r = csv.reader(f); next(r, None)
        for row in r:
            if len(row) >= 5: rows[row[0]] = row[:6] if len(row) >= 6 else row[:5] + ["mx"]
    return rows

def closed(t_ny):   # Fri 17:00 -> Sun 18:00 NY
    wd, h = t_ny.weekday(), t_ny.hour
    return wd == 5 or (wd == 4 and h >= 17) or (wd == 6 and h < 18)

def main():
    if not KEY: print("MASSIVE_KEY is not set", flush=True); sys.exit(1)
    rows = load_csv(); last = datetime.strptime(max(rows), "%Y-%m-%d %H:%M").replace(tzinfo=NY)
    start = (last.astimezone(timezone.utc) - timedelta(hours=1)).date(); end = datetime.now(timezone.utc).date() + timedelta(days=1)
    print(f"CSV ends {last:%Y-%m-%d %H:%M} NY; fetching {start} -> {end}", flush=True)
    added = 0; cur = start; calls = 0
    while cur <= end:
        to = min(end, cur + timedelta(days=20))
        url = f"https://api.massive.com/v2/aggs/ticker/C:XAUUSD/range/1/minute/{cur}/{to}?adjusted=true&sort=asc&limit=50000&apiKey={KEY}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "gold-chart-updater/1.0 (github actions)"})
            j = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
        except urllib.error.HTTPError as e:
            body = ""
            try: body = e.read().decode()[:300]
            except Exception: pass
            if e.code == 429: print("rate limited, waiting 20s", flush=True); time.sleep(20); continue
            print(f"Massive HTTP {e.code} for {cur} -> {to}: {body}", flush=True)
            print("key present:", bool(KEY), "| key length:", len(KEY), flush=True)
            sys.exit(2)
        calls += 1
        if j.get("status") not in ("OK", "DELAYED"): print("Massive error:", j.get("error") or j.get("status"), flush=True); sys.exit(2)
        for r in j.get("results", []):
            t = datetime.fromtimestamp(r["t"] / 1000, tz=timezone.utc).astimezone(NY)
            if closed(t): continue
            k = t.strftime("%Y-%m-%d %H:%M")
            if k not in rows: added += 1
            rows[k] = [k, f"{r['o']:.2f}", f"{r['h']:.2f}", f"{r['l']:.2f}", f"{r['c']:.2f}", "mx"]
        print(f"  {cur} -> {to}: {len(j.get('results', []))} bars", flush=True)
        cur = to + timedelta(days=1); time.sleep(13)
    # Today from Twelve Data (optional). Starts after the last Massive minute; never the forming minute.
    td_added = 0
    if TD:

        last_mx = max(k for k, v in rows.items() if v[5] == "mx")
        start_td = datetime.strptime(last_mx, "%Y-%m-%d %H:%M").replace(tzinfo=NY) + timedelta(minutes=2)   # +1 next minute, +1 for the shift below
        now_ny = datetime.now(timezone.utc).astimezone(NY).replace(second=0, microsecond=0) - timedelta(minutes=1)
        if now_ny > start_td:
            q = urllib.parse.urlencode({"symbol": "XAU/USD", "interval": "1min", "start_date": start_td.strftime("%Y-%m-%d %H:%M:%S"), "end_date": now_ny.strftime("%Y-%m-%d %H:%M:%S"),
                 "timezone": "America/New_York", "outputsize": 5000, "format": "JSON", "apikey": TD})
            try:
                j = json.loads(urllib.request.urlopen("https://api.twelvedata.com/time_series?" + q, timeout=30).read().decode())
                if j.get("status") == "error": print("Twelve Data:", j.get("message", "")[:120], flush=True)
                for v in j.get("values", []):
                    t = datetime.strptime(v["datetime"][:16], "%Y-%m-%d %H:%M") - timedelta(minutes=1)   # Twelve Data stamps candles one minute late
                    if closed(t.replace(tzinfo=NY)): continue
                    k = t.strftime("%Y-%m-%d %H:%M")
                    if k not in rows or rows[k][5] == "td":
                        if k not in rows: td_added += 1
                        rows[k] = [k, f"{float(v['open']):.2f}", f"{float(v['high']):.2f}", f"{float(v['low']):.2f}", f"{float(v['close']):.2f}", "td"]
                print(f"  today via Twelve Data: {td_added} new candles (through {now_ny:%H:%M} NY)", flush=True)
            except Exception as e: print("Twelve Data request failed:", e, flush=True)
    with CSV.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["time_ny", "open", "high", "low", "close", "src"])
        for k in sorted(rows): w.writerow(rows[k][:6])
    print(f"done: {added} Massive candles in {calls} requests, {td_added} Twelve Data candles; CSV now ends {max(rows)} NY", flush=True)

if __name__ == "__main__":
    main()
