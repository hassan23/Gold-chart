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
    # Massive: start from the last CLEAN (mx) row, so Twelve Data rows get replaced; end yesterday (UTC), the free plan has no same-day data
    last_mx_key = max(k for k, v in rows.items() if v[5] == "mx")
    last_mx = datetime.strptime(last_mx_key, "%Y-%m-%d %H:%M").replace(tzinfo=NY)
    start = (last_mx.astimezone(timezone.utc) - timedelta(hours=1)).date(); end = datetime.now(timezone.utc).date() - timedelta(days=1)
    print(f"CSV ends {last:%Y-%m-%d %H:%M} NY (clean Massive data to {last_mx:%Y-%m-%d %H:%M}); Massive range {start} -> {end}", flush=True)
    added = 0; cur = start; calls = 0; massive_ok = True
    if start > end: print("Massive: nothing new to fetch yet (free plan publishes a day after it closes)", flush=True)
    while cur <= end:
        to = min(end, cur + timedelta(days=20))
        url = f"https://api.massive.com/v2/aggs/ticker/C:XAUUSD/range/1/minute/{cur}/{to}?adjusted=true&sort=asc&limit=50000&apiKey={KEY}"
        j = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "gold-chart-updater/1.0 (github actions)"})
                j = json.loads(urllib.request.urlopen(req, timeout=60).read().decode()); break
            except urllib.error.HTTPError as e:
                body = ""
                try: body = e.read().decode()[:300]
                except Exception: pass
                print(f"Massive HTTP {e.code} for {cur} -> {to} (attempt {attempt+1}/3): {body}", flush=True)
                if e.code == 429: time.sleep(20)
                else: time.sleep(15)
            except Exception as e:
                print(f"Massive request error: {e}", flush=True); time.sleep(10)
        if j is None:
            print("Massive unavailable from this runner right now; will use Twelve Data for the gap and retry next run.", flush=True)
            massive_ok = False; break
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
        chunk = start_td; n_calls = 0
        while chunk < now_ny and n_calls < 8:          # up to 8 x 5000 minutes (~4 weeks) per run, within the free limit of 8/min
            end_c = min(now_ny, chunk + timedelta(minutes=4999))
            q = urllib.parse.urlencode({"symbol": "XAU/USD", "interval": "1min", "start_date": chunk.strftime("%Y-%m-%d %H:%M:%S"), "end_date": end_c.strftime("%Y-%m-%d %H:%M:%S"),
                 "timezone": "America/New_York", "outputsize": 5000, "format": "JSON", "apikey": TD})
            try:
                if n_calls: time.sleep(8)
                j = json.loads(urllib.request.urlopen("https://api.twelvedata.com/time_series?" + q, timeout=30).read().decode()); n_calls += 1
                if j.get("status") == "error":
                    msg = j.get("message", "")
                    if "No data" not in msg: print("Twelve Data:", msg[:120], flush=True); break
                for v in j.get("values", []):
                    t = datetime.strptime(v["datetime"][:16], "%Y-%m-%d %H:%M") - timedelta(minutes=1)   # Twelve Data stamps candles one minute late
                    if closed(t.replace(tzinfo=NY)): continue
                    k = t.strftime("%Y-%m-%d %H:%M")
                    if k not in rows or rows[k][5] == "td":
                        if k not in rows: td_added += 1
                        rows[k] = [k, f"{float(v['open']):.2f}", f"{float(v['high']):.2f}", f"{float(v['low']):.2f}", f"{float(v['close']):.2f}", "td"]
            except Exception as e: print("Twelve Data request failed:", e, flush=True); break
            chunk = end_c + timedelta(minutes=1)
        print(f"  via Twelve Data: {td_added} new candles (through {now_ny:%Y-%m-%d %H:%M} NY, {n_calls} requests)", flush=True)
    with CSV.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["time_ny", "open", "high", "low", "close", "src"])
        for k in sorted(rows): w.writerow(rows[k][:6])
    print(f"done: {added} Massive candles in {calls} requests, {td_added} Twelve Data candles; CSV now ends {max(rows)} NY", flush=True)
    if not massive_ok and td_added == 0 and added == 0: sys.exit(2)

if __name__ == "__main__":
    main()
