#!/usr/bin/env python3
"""Promoter (step L of the factory, Cleiton's request, 23 Nov 2026).
After the kit is ready, prepares the sale on the PDF channels, always as a DRAFT:
  1. printable.pdf and a 5-page sample (printable.py), if missing
  2. images: cover front, Gumroad cover and thumbnail, 3 previews, sample cover
  3. texts (Editor bot): Gumroad book + sample, Etsy, 5 pins (rule 0013 amendment 3: SEO 1st sentence + transformation)
  4. Pinterest images and pins.json (cover + 2 free + 2 from the book)
  5. Gumroad products as DRAFTS (gumroad products create --draft): book and sample
  6. Etsy draft (etsy_draft.py) only if there is a token and an approved Etsy price
  7. kit/PROMOTE.md with what is left for Cleiton to do
Never publishes, never creates accounts, never pays. Publishing (Gumroad, Etsy, Pinterest) is Cleiton's job.
Each step skips if the file already exists: it can run again without repeating work or cost.
Usage: promote.py BOOK_FOLDER [--dry-run]   (--dry-run: Gumroad with --dry-run, Etsy with --dry-run)"""
import datetime, json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

H = os.path.expanduser
P = os.path.abspath(sys.argv[1]); KIT = f"{P}/kit"; DRY_RUN = "--dry-run" in sys.argv
BIN, FT, CONFIG = H("~/books/bin"), H("~/books/fonts"), H("~/company/config.json")
GUMROAD, ETSY_SECRET = H("~/.local/bin/gumroad"), H("~/company/.secrets/etsy.json")
ENV = dict(os.environ, PATH=f"/opt/homebrew/bin:{H('~/.local/bin')}:/usr/bin:/bin:/usr/sbin:/sbin")
BACKGROUND, BROWN, TERRA, MUSTARD, BG = (253, 240, 219), (92, 58, 40), (196, 120, 86), (240, 190, 80), (251, 246, 238)
AI_DISCLOSURE = "AI-generated illustrations, edited by a human."
today = datetime.date.today().isoformat()
notes = []  # what is left for Cleiton


def lj(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d


def sj(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w"), indent=1, ensure_ascii=False)


def run(cmd, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV, stdin=subprocess.DEVNULL)


CFG = lj(CONFIG, {}) or {}
STORE = CFG.get("gumroad_store", "https://YOUR-STORE.gumroad.com/l/")
SOCIAL = CFG.get("social_links")  # block at the end of the Gumroad description (never on Etsy: Etsy rule)
BOARDS = CFG.get("pinterest_boards", ["Free Printable Coloring Pages", "Cozy Coloring Pages for Adults"])
L, st = lj(f"{P}/book.json"), lj(f"{P}/state.json", {})
lst = lj(f"{KIT}/listing.json", {})
ap = lj(f"{P}/approvals.json", {}) or {}
approved = [p for p in L["pages"] if st.get(p["id"], {}).get("state") == "approved"]
N = len(approved)
# same rule as printable.py --sample 5: 5 pages spread across the book
# decision 0024: pages coming from the image bank (from another book) are never a sample, preview or pin of this book
own = [p for p in approved if not p.get("origin")] or approved
FREE = [own[round(i * (len(own) - 1) / 4)] for i in range(min(5, len(own)))]
rest = [p for p in own if p not in FREE] or own
REUSED = [p for p in approved if p.get("origin")]
REUSE_DISCLOSURE = (f"{len(REUSED)} of the {N} scenes also appear in another MySandboxBooks book ("
                    + ", ".join(dict.fromkeys(p["origin"]["title"] for p in REUSED)) + f"); the other {N - len(REUSED)} are new."
                    if REUSED else "")
pick = lambda fr: rest[min(len(rest) - 1, int(len(rest) * fr))]
BOOK_PINS = [pick(.2), pick(.4)]
PREV1 = [pick(f) for f in (.05, .3, .55, .8)]
PREV2 = [pick(f) for f in (.15, .4, .65, .9)]
PREV3 = pick(.5)


# ----------------------------------------------------------------- 1. PDFs
def pdfs():
    if not os.path.exists(f"{KIT}/printable.pdf"):
        run([sys.executable, f"{BIN}/printable.py", P]).check_returncode()
    if not os.path.exists(f"{KIT}/sample/sample.pdf"):
        run([sys.executable, f"{BIN}/printable.py", P, "--sample", "5"]).check_returncode()


# ----------------------------------------------------------------- 2. images
def font(rel, size, var=None):
    f = ImageFont.truetype(f"{FT}/{rel}", size)
    if var:
        try: f.set_variation_by_axes(var)
        except Exception: pass
    return f


TIT = lambda s: font("cherrybombone/CherryBombOne-Regular.ttf", s)
SUB = lambda s: font("fredoka/Fredoka[wdth,wght].ttf", s, [600, 100])


def front():
    """Cover front, cropped from the full cover (bleed 0.125 in, book 8.5 x 8.5)."""
    out = f"{KIT}/etsy/cover-front.jpg"
    if not os.path.exists(out):
        cj = lj(f"{KIT}/cover.json")
        im = Image.open(f"{KIT}/cover-preview.png").convert("RGB")
        dpi = im.width / (2 * 8.625 + cj["spine_in"])
        x0, y0, side = round((0.125 + 8.5 + cj["spine_in"]) * dpi), round(0.125 * dpi), round(8.5 * dpi)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im.crop((x0, y0, x0 + side, y0 + side)).save(out, quality=92)
    return out


def resize(src, out, side):
    if not os.path.exists(out):
        im = Image.open(src).convert("RGB"); im.thumbnail((side, side), Image.LANCZOS); im.save(out, quality=90)
    return out


def card(base, pid, x, y, side):
    """Page on a white sheet with a soft shadow."""
    sh = Image.new("L", base.size, 0)
    ImageDraw.Draw(sh).rectangle([x + 10, y + 16, x + side + 10, y + side + 16], fill=90)
    base.paste((150, 120, 95), (0, 0), sh.filter(ImageFilter.GaussianBlur(14)))
    ImageDraw.Draw(base).rectangle([x, y, x + side, y + side], fill="white")
    art = Image.open(f"{P}/final/{pid}.png").convert("L")
    art.thumbnail((side - 40, side - 40), Image.LANCZOS)
    base.paste(art.convert("RGB"), (x + (side - art.width) // 2, y + (side - art.height) // 2))


def collage(pages, out, W=1600, m=70, g=50):
    if os.path.exists(out): return out
    im = Image.new("RGB", (W, W), BG); c = (W - 2 * m - g) // 2
    for i, p in enumerate(pages):
        card(im, p["id"], m + (i % 2) * (c + g), m + (i // 2) * (c + g), c)
    im.save(out, quality=90); return out


def single(p, out, W=1600, m=90):
    if os.path.exists(out): return out
    im = Image.new("RGB", (W, W), BG); card(im, p["id"], m, m, W - 2 * m); im.save(out, quality=90); return out


def sample_cover(cf):
    out = f"{KIT}/sample/cover.jpg"
    if not os.path.exists(out):
        im = Image.open(cf).convert("RGB").resize((1600, 1600), Image.LANCZOS); d = ImageDraw.Draw(im)
        txt = f"FREE SAMPLE: {len(FREE)} PAGES"; f = SUB(96)
        d.rectangle([0, 1600 - 230, 1600, 1600 - 70], fill=MUSTARD)
        d.text(((1600 - d.textlength(txt, font=f)) / 2, 1600 - 210), txt, font=f, fill=BROWN)
        im.save(out, quality=90)
    resize(out, f"{KIT}/sample/thumb.jpg", 600)
    return out


def images():
    os.makedirs(f"{KIT}/gumroad", exist_ok=True); os.makedirs(f"{KIT}/sample", exist_ok=True)
    cf = front()
    resize(cf, f"{KIT}/gumroad/cover.jpg", 1600); resize(cf, f"{KIT}/gumroad/thumb.jpg", 600)
    collage(PREV1, f"{KIT}/gumroad/preview-1.jpg"); collage(PREV2, f"{KIT}/gumroad/preview-2.jpg")
    single(PREV3, f"{KIT}/gumroad/preview-3.jpg")
    sample_cover(cf)


# ----------------------------------------------------------------- 3. texts (Editor bot)
S = lambda: {"type": "string"}
LST = lambda: {"type": "array", "items": {"type": "string"}}
OBJ = lambda props: {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
IMG_TXT = OBJ({"line1": S(), "line2": S(), "sub": S(), "pill": S()})
PIN = OBJ({"title": S(), "description": S(), "alt": S()})
SCHEMA = OBJ({
    "gumroad": OBJ({"name": S(), "summary": S(), "permalink": S(), "description_html": S(), "tags": LST(), "receipt": S()}),
    "sample": OBJ({"name": S(), "summary": S(), "permalink": S(), "description_html": S(), "tags": LST(), "receipt": S()}),
    "etsy": OBJ({"title": S(), "tags": LST(), "description": S()}),
    "pin_images": OBJ({"free": IMG_TXT, "cover": IMG_TXT, "book": IMG_TXT}),
    "book_board": S(),
    "pins": OBJ({"cover": PIN, "free_1": PIN, "free_2": PIN, "book_1": PIN, "book_2": PIN}),
    "notes": S()})


def validate(c):
    e = []
    t = c["etsy"]["title"]
    if len(t) > 140: e.append(f"Etsy title has {len(t)} characters (max 140)")
    if re.search(r"[^\w\s\.,;:!\?'\"\-\(\)&%+/]", t): e.append("Etsy title has forbidden characters")
    for ch in "%:&+":
        if t.count(ch) > 1: e.append(f"Etsy title uses '{ch}' more than once")
    tg = c["etsy"]["tags"]
    if len(tg) != 13 or len(set(tg)) != 13: e.append(f"Etsy needs 13 different tags (has {len(set(tg))})")
    e += [f"invalid Etsy tag: {g}" for g in tg if len(g) > 20 or re.search(r"[^\w\s\-']", g) or "_" in g]
    if re.search(r"https?://|www\.|instagram|tiktok", c["etsy"]["description"], re.I): e.append("Etsy description has links")
    for k in ("gumroad", "sample"):
        if len(c[k]["tags"]) > 10: e.append(f"{k}: more than 10 tags")
        if not re.fullmatch(r"[a-z0-9-]{3,60}", c[k]["permalink"]): e.append(f"{k}: invalid permalink")
    if c["gumroad"]["permalink"] == c["sample"]["permalink"]: e.append("permalinks are the same")
    for k, p in c["pins"].items():
        if len(p["title"]) > 100: e.append(f"pin {k}: title > 100")
        if len(p["description"]) > 500: e.append(f"pin {k}: description > 500")
        if len(p["alt"]) > 500: e.append(f"pin {k}: alt > 500")
    everything = json.dumps(c, ensure_ascii=False)
    if "\u2014" in everything or "\u00b7" in everything: e.append("uses a long dash or a middle dot")
    for k in ("gumroad", "sample"):
        if AI_DISCLOSURE not in c[k]["description_html"]: e.append(f"{k}: missing the AI sentence")
    if AI_DISCLOSURE not in c["etsy"]["description"]: e.append("etsy: missing the AI sentence")
    if REUSE_DISCLOSURE:
        if REUSE_DISCLOSURE not in c["gumroad"]["description_html"]: e.append("gumroad: missing the repeated scenes sentence")
        if REUSE_DISCLOSURE not in c["etsy"]["description"]: e.append("etsy: missing the repeated scenes sentence")
    if "{{BOOK_URL}}" not in c["sample"]["description_html"]: e.append("sample: missing the {{BOOK_URL}} link to the book")
    return e


def request(errors=()):
    price = (lst.get("gumroad_price") or {}).get("price")
    pg = lambda p: f"- {p['id']}: {p['theme']}"
    example = lj(H("~/books/cozy-little-corners/kit/etsy/listing.json"), {}).get("description", "")
    return "\n".join([
        "Task: write the sales texts for this coloring book for Gumroad (PDF), Etsy (PDF) and Pinterest. All in English.",
        f"Book: {L['title']}: {L.get('subtitle', '')}. Brand/collection: {L['brand']}.",
        f"File for sale: 1 PDF with {N + 2} pages ({N} designs, 1 per page, plus cover and copyright page), "
        "US Letter 8.5 x 11 in, to print at home. Free sample: 1 PDF with 5 designs from the book.",
        f"Gumroad price of the book: US$ {price}." if price else "Gumroad price of the book: not decided yet (do not write a price).",
        "The sample is free on Gumroad (the customer types 0 and downloads).",
        f"KDP listing already approved (use the same facts, do not invent others):\n{json.dumps({k: lst.get(k) for k in ('title', 'subtitle', 'description', 'keywords')}, ensure_ascii=False)}",
        "Pages of the book (id: theme):", *map(pg, approved),
        f"Pages of the free sample: {', '.join(p['id'] for p in FREE)}.",
        f"Pins: cover = color cover; free_1 = {FREE[0]['id']}; free_2 = {FREE[1]['id']}; "
        f"book_1 = {BOOK_PINS[0]['id']}; book_2 = {BOOK_PINS[1]['id']}. In the alt, describe what is seen on that page.",
        "", "Rules (decision 0013, amendment 3, from Cleiton: always like this):",
        "1. The 1st sentence of each description has the main search words: what it is, who it is for, how many pages, format.",
        "2. Then, the transformation: the scene of the moment the book gives (e.g. phone face down, hot drink, the calm evening).",
        "3. What is inside, told as an experience (scenes, character).",
        "4. Sections: WHY IT FEELS SO EASY TO START, PERFECT FOR, WHAT YOU GET, HOW TO PRINT, PLEASE NOTE, AI DISCLOSURE.",
        f"5. Mandatory AI sentence, exactly: \"{AI_DISCLOSURE}\" (Gumroad book, sample and Etsy; and at the end of each pin).",
        *([f"5b. Mandatory sentence in the PLEASE NOTE section of the Gumroad book and of Etsy, exactly: \"{REUSE_DISCLOSURE}\""]
          if REUSE_DISCLOSURE else []),
        "6. Never use a long dash (\u2014) or a middle dot (\u00b7). No strikethrough prices, fake discounts, ratings, "
        "sales numbers or promises that are not in the facts above.",
        "7. Gumroad: description_html in simple HTML (h2, h3, p, ul, li, em, a). Do not add social links (the system adds them). "
        "The sample description has a link to the book written exactly like this: <a href=\"{{BOOK_URL}}\">. Tags: up to 10, lowercase. "
        "permalink: lowercase, numbers and hyphens, with search words. receipt: 1 to 2 thank-you sentences with a printing tip.",
        "8. Etsy: plain text without HTML and WITHOUT links or social links (Etsy rule). title up to 140 characters, "
        "without repeating words, at most one of each of these: % : & +. Exactly 13 tags, each up to 20 characters, "
        "only letters, numbers, spaces, hyphens and apostrophes.",
        "9. Pinterest: title up to 100 characters, description up to 500, alt up to 500 describing the image for people who cannot see it. "
        f"book_board: pick one of these if it fits, otherwise propose a new name: {', '.join(BOARDS[1:])}.",
        "10. pin_images: text over the pin images (line1 and line2 short, up to 18 characters each; sub up to 36; "
        "pill up to 30). free = free pages; cover = cover pin; book = book pages.",
        "11. notes: in Portuguese, doubts or facts you could not confirm.",
        "", "Example approved by Cleiton (Etsy, another book; copy the structure and the tone, not the content):", example,
        *(["", "Your previous answer failed these rules, fix them:", *errors] if errors else [])])


def codex(text, out):
    f_schema = out + ".schema.json"; sj(f_schema, SCHEMA)
    fs = H("~/books/souls/Divulgador.md")
    soul = open(fs).read().strip() if os.path.exists(fs) else \
        next((b.get("soul", "") for b in lj(H("~/.openmausbot/bots.json"), []) if b.get("name") == "Editor"), "")
    r = run(["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "--output-schema", f_schema, "-o", out,
             (soul + "\n\n" if soul else "You are the Promoter.\n\n") + text +
             "\nDo not run commands that change files. Answer only with the requested JSON."], timeout=1500)
    d = lj(out)
    if d is None:
        raise RuntimeError(f"Editor failed: {r.stderr[-400:]}")
    return d


def texts():
    out = f"{KIT}/channels.json"
    c = lj(out)
    if c and not validate(c):
        return c
    errors = validate(c) if c else []
    for _ in range(2):
        c = codex(request(errors), out)
        errors = validate(c)
        if not errors:
            return c
    raise RuntimeError("Editor did not follow the rules: " + "; ".join(errors))


def social_html():
    if not SOCIAL:
        notes.append("Gumroad: config.json has no 'social_links'; the description went out without your social links.")
        return ""
    return (f"<h3>{SOCIAL['title']}</h3><p>{SOCIAL['text']}</p><p>" +
            " | ".join(f"<a href=\"{l['url']}\">{l['name']}</a>" for l in SOCIAL["links"]) + "</p>")


# ----------------------------------------------------------------- 4. Pinterest
def center(d, y, txt, f, color, W, maxw=900):
    while d.textlength(txt, font=f) > maxw:
        f = f.font_variant(size=f.size - 2)
    d.text(((W - d.textlength(txt, font=f)) / 2, y), txt, font=f, fill=color)


def pin_img(t, out, pid=None, img=None, W=1000, Hh=1500):
    if os.path.exists(out): return out
    im = Image.new("RGB", (W, Hh), BACKGROUND); d = ImageDraw.Draw(im); y = 70
    for line in (t["line1"], t["line2"]):
        center(d, y, line, TIT(92), BROWN, W); y += 104
    center(d, y + 22, t["sub"], SUB(44), TERRA, W); y += 92
    cs = 860; x0 = (W - cs) // 2; y0 = y + 20
    if img:
        sh = Image.new("L", (W, Hh), 0); ImageDraw.Draw(sh).rectangle([x0 + 10, y0 + 16, x0 + cs + 10, y0 + cs + 16], fill=90)
        im.paste((150, 120, 95), (0, 0), sh.filter(ImageFilter.GaussianBlur(14)))
        im.paste(Image.open(img).convert("RGB").resize((cs, cs), Image.LANCZOS), (x0, y0))
    else:
        card(im, pid, x0, y0, cs)
    fp = SUB(46); tw = d.textlength(t["pill"], font=fp); py = y0 + cs + 50
    d.rounded_rectangle([(W - tw) / 2 - 44, py, (W + tw) / 2 + 44, py + 84], radius=42, fill=MUSTARD)
    d.text(((W - tw) / 2, py + 14), t["pill"], font=fp, fill=BROWN)
    center(d, Hh - 80, L["brand"], SUB(40), TERRA, W)
    im.save(out, optimize=True); return out


def pinterest(c, book_url, sample_url):
    out = f"{KIT}/pinterest/pins.json"
    if os.path.exists(out):
        return
    os.makedirs(f"{KIT}/pinterest", exist_ok=True)
    ti, pins = c["pin_images"], []
    plan = [("free_1", FREE[0]["id"], "free", BOARDS[0], sample_url),
            ("free_2", FREE[1]["id"], "free", BOARDS[0], sample_url),
            ("cover", None, "cover", c["book_board"], book_url),
            ("book_1", BOOK_PINS[0]["id"], "book", c["book_board"], book_url),
            ("book_2", BOOK_PINS[1]["id"], "book", c["book_board"], book_url)]
    for k, pid, kind, board, link in plan:
        name = f"{k.replace('_', '-')}-{pid or 'cover'}.png"
        pin_img(ti[kind], f"{KIT}/pinterest/{name}", pid=pid, img=None if pid else f"{KIT}/etsy/cover-front.jpg")
        pins.append({"image": name, "board": board, "link": link,
                     **{x: c["pins"][k][x] for x in ("title", "description", "alt")},
                     "ai_label": True, "show_similar_products": False})
    sj(out, pins)
    if c["book_board"] not in BOARDS:
        notes.append(f"Pinterest: new board proposed, '{c['book_board']}' (create it before publishing).")


# ----------------------------------------------------------------- 5. Gumroad (drafts)
def gumroad(key, txt, price, pdf, pdf_name, cover, thumb, previews, pwyw=False):
    """Creates the product as a DRAFT (--draft). Saves the id in kit/<key>/... so it is never created twice."""
    f = f"{KIT}/gumroad/listing.json" if key == "book" else f"{KIT}/sample/gumroad.json"
    a = lj(f, {}) or {}
    url = STORE + txt["permalink"]
    if a.get("product"):
        return a.get("url", url)
    if price is None:
        notes.append(f"Gumroad {key}: no price in the listing (gumroad_price); draft not created.")
        return url
    desc = txt["description_html"] + social_html()
    open(f"{KIT}/gumroad/description.html" if key == "book" else f"{KIT}/sample/description.html", "w").write(desc)
    cmd = [GUMROAD, "products", "create", "--draft", "--non-interactive", "--json", "--name", txt["name"],
           "--price", str(price), "--currency", "usd", "--description", desc, "--custom-summary", txt["summary"],
           "--custom-receipt", txt["receipt"], "--custom-permalink", txt["permalink"], "--category", "drawing-and-painting",
           "--file", pdf, "--file-name", pdf_name, "--cover-image", cover, "--thumbnail", thumb] + \
          [x for p in previews for x in ("--preview-image", p)] + [x for t in txt["tags"] for x in ("--tag", t)] + \
          (["--pay-what-you-want"] if pwyw else []) + (["--dry-run"] if DRY_RUN else [])
    r = run(cmd, timeout=900)
    a.update({"title": txt["name"], "tags": txt["tags"], "category": "Drawing & Painting", "url": url,
              "permalink": txt["permalink"], "price_usd": price, "social_links": SOCIAL or "NO"})
    if r.returncode:
        notes.append(f"Gumroad {key}: the CLI failed ({(r.stderr or r.stdout)[-300:].strip()}).")
        sj(f, a); return url
    if DRY_RUN:
        print(f"[dry-run] Gumroad {key}: {r.stdout[-800:]}")
        return url
    try:
        d = json.loads(r.stdout); p = d.get("product", d)
        a.update({"product": p.get("id"), "url": p.get("short_url") or url, "state": f"draft created {today}"})
    except Exception:
        a["state"] = f"created? response not read: {r.stdout[-300:]}"
        notes.append(f"Gumroad {key}: check in the dashboard whether the draft exists (CLI response not read).")
    sj(f, a)
    return a["url"]


# ----------------------------------------------------------------- 6. Etsy (draft)
DEFAULT_ETSY_PRICE = 2.77  # decision 0027 (26 Nov 2026)
def etsy(c):
    f = f"{KIT}/etsy/listing.json"
    a = lj(f) or {"title": c["etsy"]["title"], "tags": c["etsy"]["tags"], "description": c["etsy"]["description"],
                  "digital_file": f"printable.pdf ({N + 2} pages)",
                  "photos": ["etsy/cover-front.jpg", "gumroad/preview-1.jpg", "gumroad/preview-2.jpg", "gumroad/preview-3.jpg"],
                  "price": {"eur": None, "state": "awaiting approval"}, "social_links": "NO (Etsy rule)"}
    pe = ap.get("price_etsy") or DEFAULT_ETSY_PRICE  # decision 0027: EUR 2.77 by default; approvals.json can change it
    if pe and "approved" not in (a.get("price") or {}).get("state", ""):
        a["price"] = {"eur": pe, "discount": "none (no strikethrough price)",
                      "state": f"approved Cleiton {today}" if ap.get("price_etsy") else f"approved rule 0027 {today}"}
    sj(f, a)
    if a.get("listing_id"):
        return
    if "approved" not in (a.get("price") or {}).get("state", ""):
        notes.append("Etsy: the price is missing. Approve it with \"price_etsy\": <EUR> in approvals.json (fees in decision 0013).")
        return
    if not os.path.exists(ETSY_SECRET):
        notes.append("Etsy: no API token (OAuth not done yet); the draft has to be made by hand from kit/etsy/listing.json.")
        return
    r = run([sys.executable, f"{BIN}/etsy_draft.py", P] + (["--dry-run"] if DRY_RUN else []), timeout=900)
    if r.returncode:
        notes.append(f"Etsy: draft failed ({(r.stderr or r.stdout)[-300:].strip()}).")


# ----------------------------------------------------------------- main
def main():
    pdfs(); images()
    c = texts()
    g = f"{KIT}/gumroad"
    book_url = gumroad("book", c["gumroad"], (lst.get("gumroad_price") or {}).get("price"), f"{KIT}/printable.pdf",
                       f"{L['title']} - Printable Coloring Book (US Letter).pdf", f"{g}/cover.jpg", f"{g}/thumb.jpg",
                       [f"{g}/preview-{i}.jpg" for i in (1, 2, 3)])
    txt_s = dict(c["sample"], description_html=c["sample"]["description_html"].replace(
        "{{BOOK_URL}}", book_url))
    sample_url = gumroad("sample", txt_s, 0, f"{KIT}/sample/sample.pdf",
                         f"{L['title']} - Free Sample (5 pages).pdf", f"{KIT}/sample/cover.jpg",
                         f"{KIT}/sample/thumb.jpg", [], pwyw=True)
    pinterest(c, book_url, sample_url)
    etsy(c)
    notes.append("Gumroad: review the 2 drafts and publish (Publish). The receipt page (rich content) is still by hand.")
    notes.append("Pinterest: publish the 5 pins from kit/pinterest/pins.json after Gumroad is public "
                 "(AI label on, similar products off).")
    if c.get("notes"):
        notes.append("Editor notes: " + c["notes"])
    md = [f"# Promote: {L['title']}", f"Generated {today} by the Promoter. Everything is a draft; publishing is Cleiton's job.", "",
          "## Files", "- Texts: kit/channels.json", "- Gumroad: kit/gumroad/ (cover, thumb, preview-1..3, listing.json)",
          "- Sample: kit/sample/ (sample.pdf, cover, thumb, gumroad.json)", "- Etsy: kit/etsy/listing.json",
          "- Pinterest: kit/pinterest/pins.json + 5 images", "", "## Links",
          f"- Book: {book_url}", f"- Sample: {sample_url}", "", "## Left for Cleiton", *[f"- {n}" for n in notes]]
    open(f"{KIT}/PROMOTE.md", "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
