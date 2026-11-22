#!/usr/bin/env python3
"""Dados de mercado Amazon (amazon.com, livros impressos) via Apify, decisao 0008.
Uso: mercado_amazon.py "kw 1" "kw 2" ...   [env LIVROS_POR_KW=30]
Actor: getascraper/kdp-book-niche-analyzer (pay per event, ~$0.00133/livro no plano Free).
Token em ~/.apify-pessoal (conta pessoal). Nunca imprime o token.
Saida: ~/livros/mercado/AAAA-MM-DD-HHMM.json"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request

ACTOR = "getascraper~kdp-book-niche-analyzer"
API = "https://api.apify.com/v2"
kws = [k for k in sys.argv[1:] if k.strip()]
if not kws:
    sys.exit("Indica pelo menos uma palavra-chave.")
por_kw = int(os.environ.get("LIVROS_POR_KW") or 30)
max_items = len(kws) * (por_kw + 1)
teto_usd = round(max_items * 0.0015 + 0.05, 2)  # teto duro de gasto por run

with open(os.path.expanduser("~/.apify-pessoal")) as f:
    HDR = {"Authorization": "Bearer " + f.read().strip(), "Content-Type": "application/json"}

def call(url, data=None, method=None):
    req = urllib.request.Request(url, data=data, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")

inp = {"keywords": kws, "department": "PAPERBACK", "maxBooksPerKeyword": por_kw,
       "includeAutocompleteSuggestions": True, "analyzeAutocompleteSuggestions": False,
       "includeNicheRows": True}
q = urllib.parse.urlencode({"maxItems": max_items, "maxTotalChargeUsd": teto_usd})
run = call(f"{API}/acts/{ACTOR}/runs?{q}", json.dumps(inp).encode(), "POST")["data"]
t0 = time.time()
while run["status"] in ("READY", "RUNNING"):
    if time.time() - t0 > 1800:
        sys.exit(f"Timeout; run {run['id']} ainda a correr.")
    time.sleep(15)
    run = call(f"{API}/actor-runs/{run['id']}")["data"]
if run["status"] != "SUCCEEDED":
    sys.exit(f"Run {run['id']} terminou com {run['status']}.")
items = call(f"{API}/datasets/{run['defaultDatasetId']}/items?clean=true&format=json")
out = os.path.expanduser(time.strftime("~/livros/mercado/%Y-%m-%d-%H%M.json"))
with open(out, "w") as f:
    json.dump({"keywords": kws, "run_id": run["id"], "custo_usd": run.get("usageTotalUsd"),
               "segundos": round(time.time() - t0), "itens": items}, f, ensure_ascii=False, indent=1)
print(json.dumps({"ficheiro": out, "itens": len(items), "custo_usd": run.get("usageTotalUsd"),
                  "teto_usd": teto_usd, "segundos": round(time.time() - t0)}))
