#!/usr/bin/env python3
"""Builds blocklist.txt for Valu-Shield from the FTC Do Not Call complaint API.

Each run fetches the complaints for the given day(s), stores per-day counts in
daily/YYYY-MM-DD.csv, then rebuilds blocklist.txt from the last WINDOW days:
  <E.164 digits>,<reports>   sorted ascending, unique  (what the iPhone blocker expects)

Usage:  FTC_API_KEY=xxxx python3 build_blocklist.py [days_back=3]
API key (free): https://api.data.gov/signup/
"""
import csv, datetime as dt, json, os, sys, time, urllib.parse, urllib.request
from collections import Counter
from pathlib import Path

API = "https://api.ftc.gov/v0/dnc-complaints"
WINDOW = 60          # days of complaints that make up the list
MIN_REPORTS = 1      # include numbers with at least this many reports in the window
PAGE = 50            # API maximum
PACE = 3.7           # seconds between calls: stays under api.data.gov's 1,000/hour limit
ROOT = Path(__file__).resolve().parent
DAILY = ROOT / "daily"


def e164(raw):
    d = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(d) == 10:
        d = "1" + d
    if len(d) != 11 or d[0] != "1" or d[1] in "01" or d[4] in "01":
        return None   # not a valid US/Canada number
    return int(d)


def get(params, key):
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"X-Api-Key": key, "User-Agent": "valu-shield-data"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("rate limited; waiting 10 minutes", flush=True)
                time.sleep(600)
            elif e.code >= 500:
                time.sleep(30 * (attempt + 1))
            else:
                raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(30 * (attempt + 1))
    raise RuntimeError("FTC API kept failing")


def phone_of(r):
    """The API has returned both JSON:API rows (attributes, kebab-case) and flat camelCase rows."""
    if not isinstance(r, dict):
        return None
    src = r.get("attributes") if isinstance(r.get("attributes"), dict) else r
    for k in ("company-phone-number", "companyPhoneNumber", "company_phone_number"):
        if src.get(k):
            return src[k]
    return None


def fetch_day(day, key):
    counts, offset, total = Counter(), 0, None
    while True:
        data = get({"created_date": f'"{day}"', "items_per_page": PAGE, "offset": offset,
                    "sort_order": "ASC"}, key)
        rows = data.get("data") or []
        meta = data.get("meta") or {}
        t = meta.get("records-total", meta.get("record-total"))
        if isinstance(t, (int, str)) and str(t).isdigit():
            total = int(t)
        for r in rows:
            n = e164(phone_of(r))
            if n:
                counts[n] += 1
        offset += len(rows)
        print(f"{day}: {offset}/{total if total is not None else '?'} ({len(counts)} numbers)", flush=True)
        if len(rows) < PAGE or (total is not None and offset >= total):
            return counts
        time.sleep(PACE)


def rebuild():
    cutoff = dt.date.today() - dt.timedelta(days=WINDOW)
    total = Counter()
    for f in sorted(DAILY.glob("*.csv")):
        if dt.date.fromisoformat(f.stem) < cutoff:
            f.unlink()          # keep the repo small
            continue
        with f.open() as fh:
            for n, c in csv.reader(fh):
                total[int(n)] += int(c)
    nums = sorted(n for n, c in total.items() if c >= MIN_REPORTS)
    tmp = ROOT / "blocklist.txt.tmp"
    tmp.write_text("".join(f"{n},{total[n]}\n" for n in nums))
    tmp.replace(ROOT / "blocklist.txt")
    (ROOT / "meta.json").write_text(json.dumps({
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "count": len(nums), "windowDays": WINDOW}, indent=1))
    print(f"blocklist.txt: {len(nums)} numbers")


def main():
    key = os.environ.get("FTC_API_KEY")
    if not key:
        sys.exit("Set FTC_API_KEY (free at https://api.data.gov/signup/)")
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    DAILY.mkdir(exist_ok=True)
    today = dt.date.today()
    for i in range(days_back, 0, -1):
        day = (today - dt.timedelta(days=i)).isoformat()
        out = DAILY / f"{day}.csv"
        if out.exists() and i > 3:
            continue   # older days are final; the last 3 are re-fetched because the FTC posts with a delay
        counts = fetch_day(day, key)
        with out.open("w", newline="") as fh:
            csv.writer(fh).writerows(sorted(counts.items()))
    rebuild()


if __name__ == "__main__":
    main()
