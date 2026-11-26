#!/usr/bin/env python3
"""Rebuilds the "Log Sales" tab of the personal Google Sheet with the Gumroad sales of the coloring books.
ONE ROW PER SALE. Never writes emails or buyer data (only date, product, amount, status).
Only products with "coloring" in the name (the Gumroad account has other products that are not part of this business).
Etsy and KDP: no API access yet; they come in when there is.
Usage: sales.py   (reads SHEET_ID from ~/company/config.json -> "books_sheet")"""
import datetime, json, os, subprocess, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gsheets as g

HOME = os.path.expanduser("~")
SID = json.load(open(f"{HOME}/company/config.json"))["books_sheet"]
TAB = "Log Sales"
GR = f"{HOME}/.local/bin/gumroad"


def gum(*a):
    r = subprocess.run([GR, *a, "--json"], capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
    if r.returncode:
        sys.exit("gumroad: " + (r.stderr or r.stdout)[-300:])
    return json.loads(r.stdout)


prods = {p["name"]: p["id"] for p in gum("products", "list")["products"] if "coloring" in p["name"].lower()}
sales = [s for s in gum("sales", "list", "--all")["sales"] if s.get("product_name") in prods]
sales.sort(key=lambda s: s.get("created_at", ""))

HEADER = ["Date", "Channel", "Product", "Price (USD)", "Gumroad Total (text)", "Currency", "Free or Paid", "Refunded",
          "Sale ID", "Updated"]
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
rows = [HEADER]
for s in sales:
    price = (s.get("price") or 0) / 100  # Gumroad API v2: price in cents
    rows.append([s.get("created_at", "")[:10], "Gumroad", s.get("product_name", ""), price,
                 s.get("formatted_total_price", ""), (s.get("currency") or "").upper(),
                 "Paid" if price > 0 else "Free", "Yes" if s.get("refunded") else "No", s.get("id", ""), now])

tk = g.token()
rng = urllib.parse.quote(f"'{TAB}'!A1:Z5000")
g.api("POST", g.BASE + SID + f"/values/{rng}:clear", {}, tk=tk)
g.api("PUT", g.BASE + SID + f"/values/{urllib.parse.quote(chr(39) + TAB + chr(39) + '!A1')}?valueInputOption=USER_ENTERED",
      {"values": rows}, tk=tk)
paid = [l for l in rows[1:] if l[6] == "Paid" and l[7] == "No"]
print(json.dumps({"sales": len(rows) - 1, "paid": len(paid), "revenue_usd": round(sum(l[3] for l in paid), 2)}))
