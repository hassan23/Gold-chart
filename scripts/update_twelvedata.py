#!/usr/bin/env python3
"""Extend data/XAUUSD_1m.csv with new 1-minute XAU/USD candles from Twelve Data.
Needs the environment variable TWELVEDATA_KEY (free key from twelvedata.com).

- Fetches every 1-minute XAU/USD candle after the last one in the CSV, up to now.
- Candles are requested in New York time, matching the CSV.
- Free plan: 8 requests/minute, 800/day. Each request covers up to 5000 minutes (~3.5 days),
  so a week-long gap is 2-3 requests and an hourly top-up is 1.
"""
import csv, json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "data" / "XAUUSD_1m.csv"
NY = ZoneInfo("America/New_York")
KEY = os.environ.get("TWELVEDATA_KEY", "").strip()

def load_csv():
    rows = {}
    with CSV.open() as f:
        r = csv.reader(f); next(r, None)
        for row in r:
            if len(row) >= 5: rows[row[0]] = row
    return rows

def fetch(start: datetime, end: datetime):
    q = urllib.parse.urlencode({"symbol": "XAU/USD", "interval": "1min", "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
         "end_date": end.strftime("%Y-%m-%d %H:%M:%S"), "timezone": "America/New_York", "outputsize": 5000, "format": "JSON", "apikey": KEY})
    with urllib.request.urlopen("https://api.twelvedata.com/time_series?" + q, timeout=30) as r:
        return json.loads(r.read().decode())

def main():
    if not KEY: print("TWELVEDATA_KEY is not set", flush=True); sys.exit(1)
    rows = load_csv(); last = datetime.strptime(max(rows), "%Y-%m-%d %H:%M").replace(tzinfo=NY)
    now = datetime.now(timezone.utc).astimezone(NY)
    added = 0; calls = 0
    start = last + timedelta(minutes=2)   # +1 for the next minute, +1 for the one-minute shift applied below
    print(f"CSV ends {last:%Y-%m-%d %H:%M} NY; fetching up to {now:%Y-%m-%d %H:%M} NY", flush=True)
    while start < now:
        end = min(now, start + timedelta(minutes=4999))
        if calls: time.sleep(8)           # stay under 8 requests/minute
        j = fetch(start, end); calls += 1
        if j.get("status") == "error":
            msg = j.get("message", "")
            if "No data" in msg or "not available" in msg.lower(): print(f"  {start:%m-%d %H:%M} -> {end:%m-%d %H:%M}: no data (market closed)", flush=True); start = end + timedelta(minutes=1); continue
            print("Twelve Data error:", msg, flush=True); sys.exit(2)
        vals = j.get("values", [])
        for v in vals:
            # Twelve Data stamps each candle one minute later than other feeds (verified against Dukascopy); shift back
            t = datetime.strptime(v["datetime"][:16], "%Y-%m-%d %H:%M") - timedelta(minutes=1); k = t.strftime("%Y-%m-%d %H:%M"); wd = t.weekday()
            if wd == 5 or (wd == 4 and t.hour >= 17) or (wd == 6 and t.hour < 18): continue   # market closed
            if k not in rows: added += 1
            rows[k] = [k, f"{float(v['open']):.3f}", f"{float(v['high']):.3f}", f"{float(v['low']):.3f}", f"{float(v['close']):.3f}", v.get("volume", "0") or "0"]
        print(f"  {start:%m-%d %H:%M} -> {end:%m-%d %H:%M}: {len(vals)} candles", flush=True)
        start = end + timedelta(minutes=1)
    with CSV.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["time_ny", "open", "high", "low", "close", "volume"])
        for k in sorted(rows): w.writerow(rows[k])
    print(f"done: {added} new candles in {calls} requests; CSV now ends {max(rows)} NY", flush=True)

if __name__ == "__main__":
    main()
