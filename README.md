# Gold chart (XAU/USD), self-updating

A single-page candlestick chart with one year of 1-minute spot gold data, sessions, previous-day levels,
Camarilla pivots, replay, drawings, your trade log and a live feed. The data file is refreshed every hour
by a GitHub Action that pulls from Dukascopy's public feed, so the chart never has gaps.

## Set it up (about 5 minutes, no commands)

1. On GitHub, create a **new private repository** (any name, e.g. `gold-chart`). Don't add a README.
2. Click **uploading an existing file** and drag the *contents* of this folder in
   (`index.html`, `README.md`, `.nojekyll`, the `data`, `scripts` and `.github` folders). Commit to `main`.
   - If the web uploader refuses the `.github` folder, use GitHub Desktop or `git` once; folders starting
     with a dot sometimes need that.
3. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
4. **Settings → Actions → General → Workflow permissions: Read and write permissions.** Save.
   (This lets the hourly job commit the updated CSV.)
5. Go to the **Actions** tab, open **Update gold data**, click **Run workflow** once. It fills everything
   from where the CSV ends up to the current hour.
6. The **Publish chart** workflow runs on every push. When it finishes, the URL is shown on the Pages
   settings page: `https://<your-user>.github.io/<repo>/`.

## How it stays current

- `scripts/update_data.py` downloads completed days as 1-minute candle files and the current day as
  hourly tick files (built into 1-minute candles). Times in the CSV are New York wall-clock.
- `.github/workflows/update.yml` runs it at 7 minutes past every hour and commits `data/XAUUSD_1m.csv`
  if anything changed. Cost: about 1 minute of the free 2,000 Actions minutes per run.
- In the browser, the page loads the CSV, adds any live candles it saved locally (IndexedDB), then
  connects to Finnhub for live ticks if you've entered a key. Data from the CSV always wins over
  candles built from live ticks for the same minute.

## Keys

Finnhub (live ticks) and Twelve Data (optional manual gap fill) keys are entered in the page and kept in
your browser only. Nothing in this repository contains a key.

## Privacy and data terms

Dukascopy data is for personal use and Finnhub's terms forbid redistribution: keep the repository private
and don't share the Pages URL. Note that GitHub Pages sites on free private repositories are public URLs
(unguessable but not password-protected). If you want a login in front of it, Cloudflare Pages + Cloudflare
Access is the free option.

## Running locally instead

`python -m http.server 8000` inside this folder, then open `http://localhost:8000/`. Run
`python scripts/update_data.py` whenever you want to top up the data (Python 3.9+, no extra packages).
