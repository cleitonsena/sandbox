#!/usr/bin/env python3
"""stores: images of the competitors' books taken from their OWN STORES (Cleiton, 25 Nov 2026, decision 0021).

Rules:
- Only domains from the board's list (config.json "competitor_stores"). Never Amazon, Etsy or Gumroad:
  Amazon because of decision 0004, Etsy and Gumroad because of their terms (no content collection).
- Each URL is only requested if the store's robots.txt allows it for User-agent * (longest rule wins, with * and $).
- Only reads public product pages. Never cart, checkout, account, forms.
- Today it only knows how to read Shopify stores (/products.json and /products/<handle>.js). Other stores: skips and says why.
- Text in robots.txt that is not a rule (e.g. recommendations for agents) is ignored.
Standalone use: stores.py OUT_FOLDER "christmas coloring" example-store.com [other.com ...]
"""
import json, os, re, sys, time, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Macintosh; manual coloring book benchmark)"
FORBIDDEN = ("amazon.", "amzn.", "etsy.", "etsystatic.", "gumroad.")
_robots = {}


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _rules(domain):
    """Allow/Disallow rules of the User-agent: * group (no support for groups of a specific agent)."""
    if domain in _robots:
        return _robots[domain]
    try:
        txt = _get(f"https://{domain}/robots.txt").decode("utf-8", "replace")
    except Exception:
        _robots[domain] = None  # no readable robots.txt: do not risk it
        return None
    rules, group, agents, in_rules = [], False, [], False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (s.strip() for s in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if in_rules:
                agents, in_rules = [], False
            agents.append(v.lower())
            group = "*" in agents
        elif k in ("allow", "disallow"):
            in_rules = True
            if group and v:
                rules.append((k == "allow", v))
    _robots[domain] = rules
    return rules


def _matches(pattern, path):
    rx = "^" + re.escape(pattern).replace(r"\*", ".*")
    if rx.endswith(r"\$"):
        rx = rx[:-2] + "$"
    return re.match(rx, path) is not None


def allowed(url):
    u = urllib.parse.urlparse(url)
    domain = u.netloc.lower()
    if any(p in domain for p in FORBIDDEN):
        return False
    rules = _rules(domain)
    if rules is None:
        return False
    path = (u.path or "/") + (("?" + u.query) if u.query else "")
    best = None  # longest rule wins; tie: allow wins (like Google)
    for allow, pattern in rules:
        if _matches(pattern, path):
            if best is None or len(pattern) > len(best[1]) or (len(pattern) == len(best[1]) and allow):
                best = (allow, pattern)
    return True if best is None else best[0]


def _json(url):
    if not allowed(url):
        raise PermissionError(f"robots.txt does not allow: {url}")
    time.sleep(1)  # go slow with other people's stores
    return json.loads(_get(url))


def products(domain, query, max_prod=4):
    """Coloring products of the store whose title has all the words of the query."""
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if w not in ("book", "books", "for", "adults", "and")]
    found = []
    for page in range(1, 6):
        batch = _json(f"https://{domain}/products.json?limit=250&page={page}").get("products") or []
        if not batch:
            break
        for p in batch:
            t = (p.get("title", "") + " " + p.get("product_type", "")).lower().replace("colouring", "coloring")
            if all(w in t for w in words):
                found.append(p)
    return found[:max_prod]


def sheet(out, query, domains, per_product=6, side=400):
    """Downloads images and builds sheet-stores.png. Returns (list_of_sheets, notes)."""
    from PIL import Image, ImageDraw
    os.makedirs(f"{out}/img-stores", exist_ok=True)
    batch, notes = [], []
    for dom in domains:
        dom = dom.lower().strip()
        if any(p in dom for p in FORBIDDEN):
            notes.append(f"{dom}: skipped (forbidden: Amazon 0004, Etsy/Gumroad by their terms)")
            continue
        try:
            ps = products(dom, query)
        except PermissionError as e:
            notes.append(f"{dom}: skipped ({e})")
            continue
        except Exception as e:
            notes.append(f"{dom}: could not read the store as Shopify ({type(e).__name__})")
            continue
        if not ps:
            notes.append(f"{dom}: no product with '{query}'")
        for i, p in enumerate(ps):
            page = f"https://{dom}/products/{p['handle']}"
            if not allowed(page):
                notes.append(f"{page}: robots.txt does not allow it")
                continue
            n = 0
            for j, im in enumerate(p.get("images") or []):
                if n >= per_product:
                    break
                url = im["src"] + ("&" if "?" in im["src"] else "?") + "width=600"
                if not allowed(url):
                    continue
                f = f"{out}/img-stores/{re.sub('[^a-z0-9]+', '-', dom)}-{p['handle'][:40]}-{j + 1}.jpg"
                try:
                    if not os.path.exists(f):
                        time.sleep(0.5)
                        open(f, "wb").write(_get(url))
                    batch.append((f"{dom} {i + 1}.{j + 1}", f))
                    n += 1
                except Exception as e:
                    notes.append(f"{url}: failed ({type(e).__name__})")
            notes.append(f"{dom}: '{p['title']}' ({page}), {n} images")
    if not batch:
        return [], notes
    batch = batch[:24]
    sh = Image.new("RGB", (4 * (side + 10) + 10, ((len(batch) + 3) // 4) * (side + 40) + 10), "white")
    d = ImageDraw.Draw(sh)
    for k, (label, f) in enumerate(batch):
        im = Image.open(f).convert("RGB"); im.thumbnail((side, side))
        x, y = 10 + (k % 4) * (side + 10), 10 + (k // 4) * (side + 40)
        d.text((x, y), label, fill="black"); sh.paste(im, (x, y + 25))
    sh.save(f"{out}/sheet-stores.png")
    return [f"{out}/sheet-stores.png"], notes


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    fs, ns = sheet(sys.argv[1], sys.argv[2], sys.argv[3:])
    print("\n".join(ns))
    print(json.dumps({"sheets": fs}))
