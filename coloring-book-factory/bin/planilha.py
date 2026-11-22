#!/usr/bin/env python3
"""Reconstroi a aba "Livros" da Google Sheet pessoal: uma coluna por livro produzido.
Fontes: ~/livros/<livro>/kit/metricas.json, kit/drive.json, kit/precos.json (ou benchmark.json), ~/empresa/gastos.jsonl.
Uso: planilha.py  (le SHEET_ID de ~/empresa/config.json -> "sheet_livros")"""
import glob, json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gsheets as g
import fabrica as f

HOME = os.path.expanduser("~")
CFG = json.load(open(f"{HOME}/empresa/config.json"))
SID = CFG["sheet_livros"]
ABA = "Livros"
IRPF = CFG.get("irpf_estimado", 0.30)
RET = CFG.get("retencao_eua", 0.05)

def lj(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d

def gastos(slug):
    out = {"pesquisa": 0.0, "paginas": 0.0, "capa": 0.0, "outros": 0.0}
    for l in open(f"{HOME}/empresa/gastos.jsonl"):
        try:
            e = json.loads(l)
        except Exception:
            continue
        d = e.get("desc", "").lower()
        if slug not in d:
            continue
        k = "capa" if "capa" in d else "paginas" if "pagina" in d else "pesquisa" if ("benchmark" in d or "apify" in d) else "outros"
        out[k] += float(e.get("usd", 0))
    return {k: round(v, 2) for k, v in out.items()}

def precos(pasta):
    p = lj(f"{pasta}/kit/precos.json")
    if p:
        return p
    b = lj(f"{pasta}/benchmark.json", {}) or {}
    t = b.get("precos", {})
    return {c: {"mediana": (t.get(c) or {}).get("mediana_concorrencia"), "fonte": "benchmark.json",
                "preco": (t.get(c) or {}).get("preco"), "estado": "proposta"} for c in ("kdp", "gumroad")}

SEP = ","
def link(url, txt):
    return f'=HYPERLINK("{url}"{SEP}"{txt}")' if url else ""

def usd(x):
    return "" if x is None else round(x, 2)

tk = g.token()
_loc = g.api("GET", g.BASE + SID + "?fields=properties.locale", tk=tk)["properties"].get("locale", "en_US")
if not _loc.startswith(("en", "zh", "ja", "ko", "th")):
    SEP = ";"

livros = []
for m in sorted(glob.glob(f"{HOME}/livros/*/kit/metricas.json")):
    pasta = os.path.dirname(os.path.dirname(m))
    slug = os.path.basename(pasta)
    met = lj(m, {})
    dr = lj(f"{pasta}/kit/drive.json", {}) or {}
    ga = gastos(slug)
    total = round(sum(ga.values()), 2) or met.get("gasto_registado_usd", 0)
    pr = precos(pasta)
    col = {"nome": met.get("livro", slug), "dr": dr, "ga": ga, "total": total, "met": met, "canais": {}}
    for c in ("kdp", "gumroad"):
        x = pr.get(c) or {}
        p = x.get("preco")
        liq = f.liquido(c, p, met.get("paginas_kdp", 102 if c == "kdp" else 0)) if p else None
        col["canais"][c] = {**x, "fica": liq, "paga": (liq is not None and liq >= total),
                            "lucro": liq * (1 - IRPF) if liq is not None else None}
    livros.append(col)

L = []
def row(rotulo, vals):
    L.append([rotulo] + vals)

row("LIVRO", [link(f"https://drive.google.com/drive/folders/{b['dr'].get('pasta')}" if b['dr'].get('pasta') else "", b["nome"]) or b["nome"] for b in livros])
row("Estado", [b["dr"].get("estado", "") for b in livros])
row("Amostra gratis (5 paginas)", [link(f"https://drive.google.com/file/d/{b['dr']['amostra']}/view", "abrir") if b["dr"].get("amostra") else "" for b in livros])
row("Paginas para colorir", [b["met"].get("aprovadas", "") for b in livros])
row("", [])
row("CUSTOS DE PRODUCAO (USD, uma vez so)", [])
row("Pesquisa de mercado", [b["ga"]["pesquisa"] for b in livros])
row("Desenhos das paginas", [b["ga"]["paginas"] for b in livros])
row("Capa", [b["ga"]["capa"] for b in livros])
row("Textos, revisao e ficha (Codex, assinatura)", [0 for b in livros])
row("Outros", [b["ga"]["outros"] for b in livros])
row("TOTAL producao", [b["total"] for b in livros])
row("Imagens geradas", [b["met"].get("imagens_geradas", "") for b in livros])
row("Custo por pagina aprovada", [b["met"].get("custo_por_pagina_aprovada_usd", "") for b in livros])
for c, nome in (("kdp", "AMAZON KDP (livro impresso)"), ("gumroad", "GUMROAD (PDF para imprimir)")):
    row("", [])
    row(nome, [])
    row("Preco medio da concorrencia", [usd(b["canais"][c].get("mediana")) for b in livros])
    row("De onde vem esse preco", [b["canais"][c].get("fonte", "") for b in livros])
    row("Nosso preco", [usd(b["canais"][c].get("preco")) for b in livros])
    row("Situacao do preco", [b["canais"][c].get("estado", "") for b in livros])
    row("Fica por venda (depois da plataforma)", [usd(b["canais"][c]["fica"]) for b in livros])
    row("A 1a venda paga a producao?", [("Sim" if b["canais"][c]["paga"] else "Nao") if b["canais"][c]["fica"] is not None else "" for b in livros])
    row("Lucro por venda depois do IRPF (a partir da 2a)", [usd(b["canais"][c]["lucro"]) for b in livros])
row("", [])
row("NOTAS", [])
row("Impostos", [f"KDP: retencao EUA {int(RET*100)}% (W-8BEN, NAO VERIFICADO). IRPF estimado {int(IRPF*100)}% sobre o lucro (confirmar com gestor)."])
row("Atualizado", [__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")])

meta = g.api("GET", g.BASE + SID + "?fields=sheets.properties", tk=tk)
abas = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
if ABA not in abas:
    r = g.api("POST", g.BASE + SID + ":batchUpdate", {"requests": [{"addSheet": {"properties": {"title": ABA, "index": 0}}}]}, tk=tk)
    abas[ABA] = r["replies"][0]["addSheet"]["properties"]["sheetId"]
gid = abas[ABA]
rng = urllib.parse.quote(f"'{ABA}'!A1:Z200")
g.api("POST", g.BASE + SID + f"/values/{rng}:clear", {}, tk=tk)
g.api("PUT", g.BASE + SID + f"/values/{urllib.parse.quote(ABA + '!A1')}?valueInputOption=USER_ENTERED", {"values": L}, tk=tk)
secoes = [i for i, r in enumerate(L) if r and r[0].isupper() and r[0] not in ("",)]
req = [{"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 330}, "fields": "pixelSize"}},
       {"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 1 + max(1, len(livros))}, "properties": {"pixelSize": 230}, "fields": "pixelSize"}},
       {"repeatCell": {"range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": len(L), "startColumnIndex": 0, "endColumnIndex": 1 + len(livros)},
                       "cell": {"userEnteredFormat": {"textFormat": {"bold": False}, "wrapStrategy": "WRAP", "verticalAlignment": "TOP"}}, "fields": "userEnteredFormat(textFormat.bold,wrapStrategy,verticalAlignment)"}},
       {"updateSheetProperties": {"properties": {"sheetId": gid, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1}}, "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}}]
for i in secoes:
    req.append({"repeatCell": {"range": {"sheetId": gid, "startRowIndex": i, "endRowIndex": i + 1, "startColumnIndex": 0, "endColumnIndex": 1 + len(livros)},
                               "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.93, "green": 0.9, "blue": 0.85}}},
                               "fields": "userEnteredFormat(textFormat.bold,backgroundColor)"}})
g.api("POST", g.BASE + SID + ":batchUpdate", {"requests": req}, tk=tk)
print(f"OK: aba {ABA}, {len(livros)} livro(s), {len(L)} linhas")
