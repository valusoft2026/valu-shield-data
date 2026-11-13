# valu-shield-data

Data the Valu-Shield iPhone app downloads. No server needed — GitHub serves it.

- `blocklist.txt` — numbers reported to the FTC Do Not Call complaint system in the last 60 days, as `<E.164>,<reports>`, sorted. Rebuilt daily by GitHub Actions.
- `brokers.json` — people-search / data-broker sites and how to opt out. Edit this to fix a broken link; the app picks it up on its next daily refresh (no App Store update needed).
- `daily/` — per-day report counts (old days are pruned automatically).

## Setup (once)
1. Get a free API key: https://api.data.gov/signup/
2. Repo → Settings → Secrets and variables → Actions → New secret `FTC_API_KEY`.
3. Actions → "Build scam blocklist" → Run workflow with days `30`, then again with `60`.
   (The API allows ~1,000 calls/hour, so each backfill takes a few hours.)

FTC data is public domain.
