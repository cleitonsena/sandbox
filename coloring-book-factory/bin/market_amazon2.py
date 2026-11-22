#!/usr/bin/env python3
"""Amazon data via Apify junglee/Amazon-crawler (decision 0008). Brings BSR and purchases/month.
Usage: market_amazon2.py "kw 1" "kw 2" ...   [env BOOKS_PER_KW=16]
~$0.005/book on the Free plan. Token in ~/.apify-personal (personal account). Never prints the token."""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
ACTOR, API = "junglee~Amazon-crawler", "https://api.apify.com/v2"
kws = [k for k in sys.argv[1:] if k.strip()] or sys.exit("Give keywords.")
n = int(os.environ.get("BOOKS_PER_KW") or 16)
cap = round(len(kws) * n * 0.006 + 0.05, 2)
with open(os.path.expanduser("~/.apify-personal")) as f:
    HDR = {"Authorization": "Bearer " + f.read().strip(), "Content-Type": "application/json"}
def call(url, data=None, method=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=HDR, method=method), timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")
urls = [{"url": "https://www.amazon.com/s?" + urllib.parse.urlencode({"k": k, "i": "stripbooks"})} for k in kws]
inp = {"categoryOrProductUrls": urls, "maxItemsPerStartUrl": n, "scrapeProductDetails": True,
       "maxOffers": 0, "scrapeSellers": False, "proxyCountry": "US"}
q = urllib.parse.urlencode({"maxItems": len(kws) * n, "maxTotalChargeUsd": cap})
run = call(f"{API}/acts/{ACTOR}/runs?{q}", json.dumps(inp).encode(), "POST")["data"]
t0 = time.time()
while run["status"] in ("READY", "RUNNING"):
    if time.time() - t0 > 1800: sys.exit(f"Timeout; run {run['id']}")
    time.sleep(15); run = call(f"{API}/actor-runs/{run['id']}")["data"]
items = call(f"{API}/datasets/{run['defaultDatasetId']}/items?clean=true&format=json")
out = os.path.expanduser(time.strftime("~/books/market/%Y-%m-%d-%H%M-junglee.json"))
json.dump({"keywords": kws, "run_id": run["id"], "status": run["status"], "cost_usd": run.get("usageTotalUsd"),
           "items": items}, open(out, "w"), ensure_ascii=False, indent=1)
print(json.dumps({"file": out, "status": run["status"], "items": len(items),
                  "cost_usd": run.get("usageTotalUsd"), "cap_usd": cap, "seconds": round(time.time() - t0)}))
