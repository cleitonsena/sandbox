#!/usr/bin/env python3
"""Dados Amazon via Apify junglee/Amazon-crawler (decisao 0008). Traz BSR e compras/mes.
Uso: mercado_amazon2.py "kw 1" "kw 2" ...   [env LIVROS_POR_KW=16]
~$0.005/livro no plano Free. Token em ~/.apify-pessoal (conta pessoal). Nunca imprime o token."""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
ACTOR, API = "junglee~Amazon-crawler", "https://api.apify.com/v2"
kws = [k for k in sys.argv[1:] if k.strip()] or sys.exit("Indica palavras-chave.")
n = int(os.environ.get("LIVROS_POR_KW") or 16)
teto = round(len(kws) * n * 0.006 + 0.05, 2)
with open(os.path.expanduser("~/.apify-pessoal")) as f:
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
q = urllib.parse.urlencode({"maxItems": len(kws) * n, "maxTotalChargeUsd": teto})
run = call(f"{API}/acts/{ACTOR}/runs?{q}", json.dumps(inp).encode(), "POST")["data"]
t0 = time.time()
while run["status"] in ("READY", "RUNNING"):
    if time.time() - t0 > 1800: sys.exit(f"Timeout; run {run['id']}")
    time.sleep(15); run = call(f"{API}/actor-runs/{run['id']}")["data"]
items = call(f"{API}/datasets/{run['defaultDatasetId']}/items?clean=true&format=json")
out = os.path.expanduser(time.strftime("~/livros/mercado/%Y-%m-%d-%H%M-junglee.json"))
json.dump({"keywords": kws, "run_id": run["id"], "status": run["status"], "custo_usd": run.get("usageTotalUsd"),
           "itens": items}, open(out, "w"), ensure_ascii=False, indent=1)
print(json.dumps({"ficheiro": out, "status": run["status"], "itens": len(items),
                  "custo_usd": run.get("usageTotalUsd"), "teto_usd": teto, "segundos": round(time.time() - t0)}))
