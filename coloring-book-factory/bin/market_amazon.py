#!/usr/bin/env python3
"""Amazon market data (amazon.com, printed books) via Apify, decision 0008.
Usage: market_amazon.py "kw 1" "kw 2" ...   [env BOOKS_PER_KW=30]
Actor: getascraper/kdp-book-niche-analyzer (pay per event, ~$0.00133/book on the Free plan).
Token in ~/.apify-personal (personal account). Never prints the token.
Output: ~/books/market/YYYY-MM-DD-HHMM.json"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request

ACTOR = "getascraper~kdp-book-niche-analyzer"
API = "https://api.apify.com/v2"
kws = [k for k in sys.argv[1:] if k.strip()]
if not kws:
    sys.exit("Give at least one keyword.")
per_kw = int(os.environ.get("BOOKS_PER_KW") or 30)
max_items = len(kws) * (per_kw + 1)
cap_usd = round(max_items * 0.0015 + 0.05, 2)  # hard spend cap per run

with open(os.path.expanduser("~/.apify-personal")) as f:
    HDR = {"Authorization": "Bearer " + f.read().strip(), "Content-Type": "application/json"}

def call(url, data=None, method=None):
    req = urllib.request.Request(url, data=data, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")

inp = {"keywords": kws, "department": "PAPERBACK", "maxBooksPerKeyword": per_kw,
       "includeAutocompleteSuggestions": True, "analyzeAutocompleteSuggestions": False,
       "includeNicheRows": True}
q = urllib.parse.urlencode({"maxItems": max_items, "maxTotalChargeUsd": cap_usd})
run = call(f"{API}/acts/{ACTOR}/runs?{q}", json.dumps(inp).encode(), "POST")["data"]
t0 = time.time()
while run["status"] in ("READY", "RUNNING"):
    if time.time() - t0 > 1800:
        sys.exit(f"Timeout; run {run['id']} still running.")
    time.sleep(15)
    run = call(f"{API}/actor-runs/{run['id']}")["data"]
if run["status"] != "SUCCEEDED":
    sys.exit(f"Run {run['id']} ended with {run['status']}.")
items = call(f"{API}/datasets/{run['defaultDatasetId']}/items?clean=true&format=json")
out = os.path.expanduser(time.strftime("~/books/market/%Y-%m-%d-%H%M.json"))
with open(out, "w") as f:
    json.dump({"keywords": kws, "run_id": run["id"], "cost_usd": run.get("usageTotalUsd"),
               "seconds": round(time.time() - t0), "items": items}, f, ensure_ascii=False, indent=1)
print(json.dumps({"file": out, "items": len(items), "cost_usd": run.get("usageTotalUsd"),
                  "cap_usd": cap_usd, "seconds": round(time.time() - t0)}))
