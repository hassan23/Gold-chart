# Gold chart (XAU/USD) that keeps itself up to date

One page: candlestick chart with a year of 1-minute spot gold, sessions, previous-day levels,
Camarilla pivots, replay, drawings, your trade log and a live feed. A GitHub Action fetches new
1-minute candles from Massive (massive.com, formerly Polygon.io) every 15 minutes and commits them.
Massive's free plan serves data through the previous day, so the CSV is complete up to yesterday; the page
covers today with Finnhub live ticks (and optionally Twelve Data to fill holes).

Files:

    index.html                       the chart page
    data/XAUUSD_1m.csv               1-minute candles, New York time (grows automatically)
    scripts/update_massive.py        fetches new candles from Massive
    .github/workflows/update.yml     every 15 minutes: run the script, commit the CSV
    .github/workflows/manual.yml     "Download latest gold data now" button in the Actions tab
    .github/workflows/pages.yml      publishes the page with GitHub Pages (optional)
    workflows-copy/                  visible copies of the workflow files (.github is a hidden folder)
    .nojekyll                        required so GitHub Pages serves the files as-is

## One-time setup

1. Create the repository and upload these files (see "Hidden folder" below for the workflows).
2. Massive key (free Currencies Basic plan at massive.com/currencies):
   Settings -> Secrets and variables -> Actions -> New repository secret
   Name: MASSIVE_KEY   Value: your key
3. Settings -> Actions -> General -> Workflow permissions -> "Read and write permissions" -> Save.
4. Actions tab -> "Download latest gold data now" -> Run workflow. The log ends with
   "done: N new candles ... CSV now ends <time> NY".
5. Hosting: Settings -> Pages -> Source "GitHub Actions" (public repo) or Cloudflare Pages (private repo).
   See HOSTING.md for the step-by-step.

## How it stays current

- Massive serves clean 1-minute XAU/USD candles (verified against Dukascopy: 0.99 correlation) through the
  previous day on the free plan. Each run fetches everything after the last saved minute. 5 requests/minute.
- Data before September 2025 is thin on Massive (about 3 quotes per minute); the page stitches those candles
  so opens match previous closes. From September 2025 on the data is full quality.
- Prints during the weekend close (Fri 17:00 -> Sun 18:00 New York) are dropped.
- The page loads the CSV, fills any holes up to yesterday from Massive (key entered in the Live panel), fills
  today from Twelve Data if you gave it that key, then connects to Finnhub for live ticks. Keys never live in
  this repository.

## Hidden folder

`.github` starts with a dot, so Finder/Explorer hide it and drag-and-drop uploads may skip it. If the
Actions tab is empty after uploading, add the files by hand: Add file -> Create new file, type the path
`.github/workflows/update.yml`, paste the contents of `workflows-copy/update.yml`, commit. Same for
`manual.yml`.

## Changing the schedule

Edit the cron line in `.github/workflows/update.yml`:
`"7,22,37,52 * * * *"` = every 15 minutes, `"7,37 * * * *"` = every 30 minutes, `"7 * * * *"` = hourly.
GitHub starts scheduled runs "at or after" the time, often a few minutes late.

## Data terms

Massive's, Twelve Data's and Finnhub's free plans are for personal, non-commercial use and forbid
redistribution. Keep the repository private if you can and do not share the Pages URL publicly.
