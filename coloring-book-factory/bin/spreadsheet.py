#!/usr/bin/env python3
"""Rebuilds the "Log Production" tab of the personal Google Sheet: ONE ROW PER BOOK, one column per metric
(table format, good for filters, comparisons and charts).
Sources: ~/books/<book>/kit/metrics.json, kit/drive.json, kit/prices.json (or benchmark.json), ~/company/spend.jsonl.
The status columns (Gumroad/KDP/Etsy Status) belong to the human: if they already have a value in the sheet, they stay;
only a new book gets an initial status taken from prices.json.
Usage: spreadsheet.py  (reads SHEET_ID from ~/company/config.json -> "books_sheet")"""
import datetime, glob, json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gsheets as g
import factory as f

HOME = os.path.expanduser("~")
CFG = json.load(open(f"{HOME}/company/config.json"))
SID = CFG["books_sheet"]
TAB = "Log Production"
IRPF = CFG.get("estimated_irpf", 0.30)

def lj(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d

def spend(slug):
    out = {"research": 0.0, "pages": 0.0, "cover": 0.0, "other": 0.0}
    for l in open(f"{HOME}/company/spend.jsonl"):
        try:
            e = json.loads(l)
        except Exception:
            continue
        d = e.get("desc", "").lower()
        if slug not in d:
            continue
        k = "cover" if "cover" in d else "pages" if "page" in d else "research" if ("benchmark" in d or "apify" in d) else "other"
        out[k] += float(e.get("usd", 0))
    return {k: round(v, 2) for k, v in out.items()}

def prices(folder):
    p = lj(f"{folder}/kit/prices.json")
    if p:
        return p
    b = lj(f"{folder}/benchmark.json", {}) or {}
    t = b.get("prices", {})
    return {c: {"median": (t.get(c) or {}).get("competitor_median"), "source": "benchmark.json",
                "price": (t.get(c) or {}).get("price"), "state": "proposed"} for c in ("kdp", "gumroad")}

def initial_status(x):
    """Initial status, only for new books (after that, whatever is in the sheet wins)."""
    e = (x or {}).get("state", "").lower()
    if not e:
        return "Not started"
    if "selling" in e or "published" in e:
        return "Selling"
    if "draft" in e:
        return "Draft"
    if "upload" in e:
        return "Upload Pending"
    return "Planned"

SEP = ","
def link(url, txt):
    return f'=HYPERLINK("{url}"{SEP}"{txt}")' if url else ""

def num(x, n=2):
    return "" if x is None or x == "" else round(float(x), n)

tk = g.token()
_loc = g.api("GET", g.BASE + SID + "?fields=properties.locale", tk=tk)["properties"].get("locale", "en_US")
if not _loc.startswith(("en", "zh", "ja", "ko", "th")):
    SEP = ";"

# columns: (header, format) ; format: None text, "usd", "usd3", "eur", "pct", "int", "dec", "date"
COLS = [("Book", None), ("Gumroad Status", None), ("KDP Status", None), ("Etsy Status", None),
        ("Kit Date", "date"), ("Pages", "int"), ("Images Generated", "int"), ("Images per Page", "dec"),
        ("First-Pass Approval %", "pct"), ("Final Review Score", "int"),
        ("Cost: Market Research (USD)", "usd"), ("Cost: Page Art (USD)", "usd"), ("Cost: Cover (USD)", "usd"),
        ("Cost: Other (USD)", "usd"), ("Total Production Cost (USD)", "usd"), ("Cost per Approved Page (USD)", "usd3"),
        ("Gumroad Competitor Median (USD)", "usd"), ("Gumroad Price (USD)", "usd"), ("Gumroad Net per Sale (USD)", "usd"),
        ("Gumroad Profit per Sale after Tax (USD)", "usd"), ("Gumroad 1st Sale Pays Production?", None),
        ("KDP Competitor Median (USD)", "usd"), ("KDP Price (USD)", "usd"), ("KDP Net per Sale (USD)", "usd"),
        ("KDP Profit per Sale after Tax (USD)", "usd"), ("KDP 1st Sale Pays Production?", None),
        ("Etsy Competitor Median (EUR)", "eur"), ("Etsy Price (EUR)", "eur"),
        ("Gumroad Price Source", None), ("KDP Price Source", None), ("Etsy Price Source", None),
        ("Drive Folder", None), ("Free Sample", None), ("Updated", None)]
H = [c for c, _ in COLS]

# statuses already written by the human (by book name)
rng_all = urllib.parse.quote(f"'{TAB}'!A1:AZ500")
before = g.api("GET", g.BASE + SID + f"/values/{rng_all}", tk=tk).get("values", [])
keep = {}
if before:
    hdr = before[0]
    for r in before[1:]:
        if r and r[0]:
            keep[r[0]] = {c: (r[i] if i < len(r) else "") for i, c in enumerate(hdr)}

now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
rows = []
for m in sorted(glob.glob(f"{HOME}/books/*/kit/metrics.json")):
    folder = os.path.dirname(os.path.dirname(m))
    slug = os.path.basename(folder)
    met = lj(m, {}) or {}
    dr = lj(f"{folder}/kit/drive.json", {}) or {}
    sp = spend(slug)
    total = round(sum(sp.values()), 2) or met.get("recorded_spend_usd", 0)
    pr = prices(folder)
    name = met.get("book", slug)
    old = keep.get(name, {})
    ch = {}
    for c in ("gumroad", "kdp"):
        x = pr.get(c) or {}
        p = x.get("price")
        net = f.net_per_sale(c, p, met.get("kdp_pages", 102 if c == "kdp" else 0)) if p else None
        ch[c] = {"med": x.get("median"), "price": p, "net": net, "source": x.get("source", ""),
                 "profit": net * (1 - IRPF) if net is not None else None,
                 "pays": "" if net is None else ("Yes" if net >= total else "No")}
    et = pr.get("etsy") or {}
    rv = (met.get("final_review") or {}).get("score")
    v = {"Book": name,
         "Gumroad Status": old.get("Gumroad Status") or initial_status(pr.get("gumroad")),
         "KDP Status": old.get("KDP Status") or initial_status(pr.get("kdp")),
         "Etsy Status": old.get("Etsy Status") or initial_status(et),
         "Kit Date": datetime.datetime.fromtimestamp(os.path.getmtime(m)).strftime("%Y-%m-%d"),
         "Pages": met.get("approved_count", ""), "Images Generated": met.get("images_generated", ""),
         "Images per Page": num(met.get("images_per_page")),
         "First-Pass Approval %": num((met.get("approved_first_try_pct") or 0) / 100, 4) if "approved_first_try_pct" in met else "",
         "Final Review Score": "" if rv is None else rv,
         "Cost: Market Research (USD)": sp["research"], "Cost: Page Art (USD)": sp["pages"],
         "Cost: Cover (USD)": sp["cover"], "Cost: Other (USD)": sp["other"],
         "Total Production Cost (USD)": total,
         "Cost per Approved Page (USD)": num(met.get("cost_per_approved_page_usd"), 3),
         "Gumroad Competitor Median (USD)": num(ch["gumroad"]["med"]), "Gumroad Price (USD)": num(ch["gumroad"]["price"]),
         "Gumroad Net per Sale (USD)": num(ch["gumroad"]["net"]), "Gumroad Profit per Sale after Tax (USD)": num(ch["gumroad"]["profit"]),
         "Gumroad 1st Sale Pays Production?": ch["gumroad"]["pays"],
         "KDP Competitor Median (USD)": num(ch["kdp"]["med"]), "KDP Price (USD)": num(ch["kdp"]["price"]),
         "KDP Net per Sale (USD)": num(ch["kdp"]["net"]), "KDP Profit per Sale after Tax (USD)": num(ch["kdp"]["profit"]),
         "KDP 1st Sale Pays Production?": ch["kdp"]["pays"],
         "Etsy Competitor Median (EUR)": num(et.get("median")), "Etsy Price (EUR)": num(et.get("price")),
         "Gumroad Price Source": ch["gumroad"]["source"], "KDP Price Source": ch["kdp"]["source"], "Etsy Price Source": et.get("source", ""),
         "Drive Folder": link(f"https://drive.google.com/drive/folders/{dr['folder']}", "open") if dr.get("folder") else "",
         "Free Sample": link(f"https://drive.google.com/file/d/{dr['sample']}/view", "open") if dr.get("sample") else "",
         "Updated": now}
    rows.append([v[c] for c in H])

L = [H] + rows
meta = g.api("GET", g.BASE + SID + "?fields=sheets.properties", tk=tk)
tabs = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
if TAB not in tabs:
    r = g.api("POST", g.BASE + SID + ":batchUpdate", {"requests": [{"addSheet": {"properties": {"title": TAB, "index": 0}}}]}, tk=tk)
    tabs[TAB] = r["replies"][0]["addSheet"]["properties"]["sheetId"]
gid = tabs[TAB]
g.api("POST", g.BASE + SID + f"/values/{rng_all}:clear", {}, tk=tk)
g.api("PUT", g.BASE + SID + f"/values/{urllib.parse.quote(chr(39) + TAB + chr(39) + '!A1')}?valueInputOption=USER_ENTERED", {"values": L}, tk=tk)

FMT = {"usd": {"type": "CURRENCY", "pattern": "[$$-409]#,##0.00"}, "usd3": {"type": "CURRENCY", "pattern": "[$$-409]#,##0.000"}, "eur": {"type": "CURRENCY", "pattern": "[$€-2] #,##0.00"},
       "pct": {"type": "PERCENT", "pattern": "0%"}, "int": {"type": "NUMBER", "pattern": "0"},
       "dec": {"type": "NUMBER", "pattern": "0.00"}, "date": {"type": "DATE", "pattern": "yyyy-mm-dd"}}
n = len(L)
req = [{"updateSheetProperties": {"properties": {"sheetId": gid, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1}},
                                  "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}},
       {"repeatCell": {"range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(H)},
                       "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE",
                                                      "backgroundColor": {"red": 0.93, "green": 0.9, "blue": 0.85}}},
                       "fields": "userEnteredFormat(textFormat.bold,wrapStrategy,verticalAlignment,backgroundColor)"}},
       {"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                                      "properties": {"pixelSize": 200}, "fields": "pixelSize"}},
       {"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": len(H)},
                                      "properties": {"pixelSize": 130}, "fields": "pixelSize"}}]
for i, (_, fm) in enumerate(COLS):
    if fm and n > 1:
        req.append({"repeatCell": {"range": {"sheetId": gid, "startRowIndex": 1, "endRowIndex": n, "startColumnIndex": i, "endColumnIndex": i + 1},
                                   "cell": {"userEnteredFormat": {"numberFormat": FMT[fm]}}, "fields": "userEnteredFormat.numberFormat"}})
g.api("POST", g.BASE + SID + ":batchUpdate", {"requests": req}, tk=tk)
print(f"OK: tab {TAB}, {len(rows)} book(s), {len(H)} columns")
