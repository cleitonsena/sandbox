#!/usr/bin/env python3
"""image_bank: approved pages from books ALREADY PUBLISHED that can go into another book (Cleiton, 25 Nov 2026, decision 0024).

Rules:
- Only published books (kit/PUBLISHED.md): their public pages are already fixed.
- Never the public pages of the source book: free sample, previews and pins (same math as promote.py).
- Each page goes into at most 2 books (the source book plus 1).
- At most 30% of the pages of a new book come from the bank.
- The new book gets a new title, cover and font (that is already the factory's normal flow).
Standalone use: image_bank.py  (lists the bank and writes ~/books/image_bank.json)
"""
import glob, json, os

BOOKS = os.path.expanduser("~/books")
MAX_FRACTION, MAX_BOOKS_PER_PAGE = 0.30, 2


def lj(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d


def public_pages(approved_pages):
    """The pages promote.py shows for free (sample, previews, pins). Copy of the math in promote.py."""
    approved_pages = [p for p in approved_pages if not p.get("origin")] or approved_pages  # same as promote.py (decision 0024)
    N = len(approved_pages)
    if not N:
        return set()
    free = [approved_pages[round(i * (N - 1) / 4)] for i in range(min(5, N))]
    rest = [p for p in approved_pages if p not in free] or approved_pages
    pick = lambda fr: rest[min(len(rest) - 1, int(len(rest) * fr))]
    used = free + [pick(f) for f in (.2, .4, .05, .3, .55, .8, .15, .65, .9, .5)]
    return {p["id"] for p in used}


def approved(folder, L=None, st=None):
    L = L or lj(f"{folder}/book.json", {}) or {}
    st = st if st is not None else (lj(f"{folder}/state.json", {}) or {})
    return [p for p in L.get("pages", []) if st.get(p["id"], {}).get("state") == "approved"]


def uses():
    """How many books use each page: (source_book, id) -> list of books that reuse it."""
    u = {}
    for f in glob.glob(f"{BOOKS}/*/book.json"):
        for p in (lj(f, {}) or {}).get("pages", []):
            o = p.get("origin")
            if o:
                u.setdefault((o["book"], o["id"]), []).append(os.path.basename(os.path.dirname(f)))
    return u


def index(exclude=()):
    """Pages available in the bank (dicts with key, book, id, theme, file, style, title, niche)."""
    u, bank = uses(), []
    for f in sorted(glob.glob(f"{BOOKS}/*/book.json")):
        folder = os.path.dirname(f)
        name = os.path.basename(folder)
        if name in exclude or name.startswith(("_", "test")) or not os.path.exists(f"{folder}/kit/PUBLISHED.md"):
            continue
        L = lj(f, {}) or {}
        appr = [p for p in approved(folder, L) if not p.get("origin")]  # a reused page never goes back into the bank
        pub = public_pages(approved(folder, L))
        for p in appr:
            fi = f"{folder}/final/{p['id']}.png"
            if p["id"] in pub or not os.path.exists(fi):
                continue
            if 1 + len(u.get((name, p["id"]), [])) >= MAX_BOOKS_PER_PAGE:
                continue
            bank.append({"key": f"{name}/{p['id']}", "book": name, "id": p["id"], "theme": p["theme"],
                         "file": fi, "style": L.get("style", ""), "title": L.get("title", ""),
                         "niche": (L.get("request") or {}).get("niche", "")})
    return bank


def maximum(n_pages):
    return int(n_pages * MAX_FRACTION)


if __name__ == "__main__":
    b = index()
    json.dump(b, open(f"{BOOKS}/image_bank.json", "w"), ensure_ascii=False, indent=1)
    per = {}
    for x in b:
        per[x["book"]] = per.get(x["book"], 0) + 1
    print(json.dumps({"pages_in_bank": len(b), "per_book": per, "max_per_book_of_50": maximum(50)}))
