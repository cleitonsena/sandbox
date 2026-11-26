#!/usr/bin/env python3
"""Amazon data fallback via SerpApi (free plan, 250 searches/month; Cleiton's request, 24 Nov 2026).
Kicks in when Apify has no balance. Writes the same format as market_amazon2.py (junglee actor fields),
so the rest of the factory does not change. Cost US$ 0 (the free plan has a hard limit, it does not charge).
Spend per keyword: 1 search + 1 per coloring book with details (BSR). Before spending, reads the balance
from the Account API (free, does not count). If it is not enough, exits with code 3 and spends nothing.
Usage: market_serpapi.py "kw 1" "kw 2" ...   [env BOOKS_PER_KW=12]
Key in ~/.serpapi (personal account). Never prints the key."""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

kws = [k for k in sys.argv[1:] if k.strip()] or sys.exit("Give keywords.")
n = int(os.environ.get("BOOKS_PER_KW") or 12)
KEY = open(os.path.expanduser("~/.serpapi")).read().strip()
BASE = "https://serpapi.com"


def get(path, **p):
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(dict(p, api_key=KEY))
    try:
        with urllib.request.urlopen(url, timeout=90) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace").replace(KEY, "***")
        raise RuntimeError(f"HTTP {e.code}: {body}")


def is_coloring(t):
    t = (t or "").lower()
    return ("coloring" in t or "colouring" in t) and not ("kids" in t and "adult" not in t)


account = get("account.json")
balance = account.get("total_searches_left") or 0
needed = len(kws) * (1 + n)
if balance < needed:
    print(json.dumps({"error": "no_balance", "balance": balance, "needed": needed,
                      "renews": account.get("plan_renewal_date")}))
    sys.exit(3)

items, t0, spent = [], time.time(), 0
for kw in kws:
    # rh n:283155 = Books department on amazon.com
    s = get("search", engine="amazon", amazon_domain="amazon.com", k=kw, rh="n:283155")
    spent += 1
    if s.get("error"):
        raise SystemExit("serpapi: " + str(s["error"])[:300])
    seen = 0
    for o in s.get("organic_results") or []:
        if seen >= n:
            break
        if not o.get("asin") or not is_coloring(o.get("title")):
            continue
        seen += 1
        p = get("search", engine="amazon_product", amazon_domain="amazon.com", asin=o["asin"])
        spent += 1
        pr, det = p.get("product_results") or {}, p.get("product_details") or {}
        ranks = []
        for r in det.get("best_sellers_rank") or []:
            m = re.search(r"#[\d,]+ in ([^(]+)", r.get("text") or "")
            ranks.append({"rank": r.get("extracted_rank"), "category": (m.group(1).strip() if m else r.get("link_text"))})
        attrs = [{"key": k, "value": det[c]} for k, c in
                 [("Publication date", "publication_date"), ("Print length", "print_length"), ("Paperback", "paperback")]
                 if det.get(c)]
        price = o.get("extracted_price") or pr.get("extracted_price")
        items.append({
            "asin": o["asin"], "title": o.get("title"),
            "author": ", ".join(a.get("name", "") for a in pr.get("authors") or []) or pr.get("brand"),
            "price": {"value": price, "currency": "$"} if price else None,
            "stars": o.get("rating") or pr.get("rating"), "reviewsCount": o.get("reviews") or pr.get("reviews"),
            "bestsellerRanks": ranks, "monthlyPurchaseVolume": o.get("bought_last_month"),
            "attributes": attrs, "url": o.get("link_clean") or o.get("link"), "thumbnailImage": o.get("thumbnail"),
            "input": kw, "source": "serpapi"})

out = os.path.expanduser(time.strftime("~/books/market/%Y-%m-%d-%H%M-serpapi.json"))
json.dump({"keywords": kws, "source": "serpapi", "status": "SUCCEEDED", "cost_usd": 0, "searches": spent,
           "items": items}, open(out, "w"), ensure_ascii=False, indent=1)
print(json.dumps({"file": out, "status": "SUCCEEDED", "items": len(items), "cost_usd": 0,
                  "searches": spent, "balance_before": balance, "seconds": round(time.time() - t0)}))
