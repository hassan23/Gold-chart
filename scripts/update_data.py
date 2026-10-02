#!/usr/bin/env python3
"""Keep data/XAUUSD_1m.csv up to date from Dukascopy's public feed.

- Completed days: downloads the day's 1-minute BID candle file.
- Today (UTC): downloads the hourly tick files that already exist and builds 1-minute candles,
  so the file is never more than about an hour behind. Those provisional candles are replaced
  by the official daily file once Dukascopy publishes it.
- Times in the CSV are New York wall-clock (America/New_York), like the original data.
Run: python scripts/update_data.py
"""
import csv, lzma, struct, sys, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "data" / "XAUUSD_1m.csv"
NY = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (gold-chart updater)"}
BASE = "https://datafeed.dukascopy.com/datafeed/XAUUSD"

def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return None

def day_candles(d: date):
    """1-minute bid candles for a UTC day -> list of (utc_time, o, h, l, c, vol)."""
    raw = get(f"{BASE}/{d.year}/{d.month-1:02d}/{d.day:02d}/BID_candles_min_1.bi5")
    if not raw: return None
    data = lzma.decompress(raw); base = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    out = []
    for i in range(0, len(data), 24):
        t, o, c, l, h, v = struct.unpack(">5if", data[i:i+24])
        if v > 0: out.append((base + timedelta(seconds=t), o/1000, h/1000, l/1000, c/1000, v))
    return out

def hour_ticks_to_candles(d: date, hour: int):
    raw = get(f"{BASE}/{d.year}/{d.month-1:02d}/{d.day:02d}/{hour:02d}h_ticks.bi5")
    if raw is None: return None
    if not raw: return []
    data = lzma.decompress(raw); base = datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc)
    bars = {}
    for i in range(0, len(data), 20):
        ms, ask, bid, av, bv = struct.unpack(">3i2f", data[i:i+20])
        t = base + timedelta(milliseconds=ms); key = t.replace(second=0, microsecond=0); p = bid / 1000
        b = bars.get(key)
        if b is None: bars[key] = [p, p, p, p, bv]
        else:
            b[1] = max(b[1], p); b[2] = min(b[2], p); b[3] = p; b[4] += bv
    return [(k, *v) for k, v in sorted(bars.items())]

def load_csv():
    rows = {}
    if CSV.exists():
        with CSV.open() as f:
            r = csv.reader(f); next(r, None)
            for row in r:
                if len(row) >= 5: rows[row[0]] = row
    return rows

def ny_key(t_utc: datetime):
    return t_utc.astimezone(NY).strftime("%Y-%m-%d %H:%M")

def main():
    rows = load_csv()
    if not rows: print("no existing CSV; nothing to extend"); sys.exit(1)
    last_key = max(rows); last_ny = datetime.strptime(last_key, "%Y-%m-%d %H:%M").replace(tzinfo=NY)
    last_utc = last_ny.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    import os
    refetch = int(os.environ.get("REFETCH_DAYS", "0") or 0)   # re-download the last N days (replaces provisional candles)
    d = (last_utc - timedelta(hours=1) - timedelta(days=refetch)).date()
    if refetch: print(f"re-fetching the last {refetch} day(s) from {d}")
    added = 0; provisional = 0
    while d < now.date():
        if d.weekday() == 5: d += timedelta(days=1); continue    # Saturday: no trading
        c = day_candles(d)
        if c is None: print("no daily file yet for", d)
        else:
            for t, o, h, l, cl, v in c:
                rows[ny_key(t)] = [ny_key(t), f"{o:.3f}", f"{h:.3f}", f"{l:.3f}", f"{cl:.3f}", f"{v:.5f}"]
            added += len(c); print("day", d, "candles", len(c))
        time.sleep(2); d += timedelta(days=1)
    today = now.date()
    if today.weekday() != 5:
        for hour in range(now.hour):
            c = hour_ticks_to_candles(today, hour)
            if not c: continue
            for t, o, h, l, cl, v in c:
                rows[ny_key(t)] = [ny_key(t), f"{o:.3f}", f"{h:.3f}", f"{l:.3f}", f"{cl:.3f}", f"{v:.5f}"]
            provisional += len(c); time.sleep(1)
    with CSV.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["time_ny", "open", "high", "low", "close", "volume"])
        for k in sorted(rows): w.writerow(rows[k])
    print(f"done: {added} candles from daily files, {provisional} provisional candles for today; last = {max(rows)} NY")

if __name__ == "__main__":
    main()
