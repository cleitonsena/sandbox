#!/usr/bin/env python3
"""Book factory (decision 0010). Runs on the Air, on its own, from the queue in ~/company/queue/.

Usage: factory.py                        -> processes the queue until each task reaches a human gate or finishes
       factory.py --status               -> only rewrites the report and the decisions inbox
       factory.py --no-book-of-the-day   -> runs without creating the book of the day
       factory.py --week                 -> forces the weekly review today

Tasks (one .json per task in ~/company/queue/, processed in name order):
  {"type": "book", "folder": "~/books/book-02"}           (folder has book.json with "request")
  {"type": "research", "id": "puzzles-seniors", "keywords": [...], "question": "..."}
Book phases: benchmark (covers, drawings, price) -> brief -> [gate: brief] -> pages -> [gate: failed pages] -> interior -> cover
-> listing -> review of the whole book (redoes pages once on its own) -> archive in ~/Finished-Books
-> kit -> retro (sprint review) -> [gate: human upload] -> done.
Human approvals: <folder>/approvals.json (written on the main Mac after the board decides).
Caps without asking: US$ 2 per book, EUR 10 per month (images + Apify), converted at the ECB rate.
Book of the day (Cleiton's rule, 23 Nov 2026): 1 new book per day while the month is below the cap;
at the cap the factory stops and asks whether to go on (gate month_cap_YYYY-MM in ~/company/approvals.json).
Never publishes, never opens Amazon, never creates accounts, never pays.
"""
import datetime, glob, json, math, os, shutil, statistics, subprocess, sys, time

H = os.path.expanduser
COMPANY, BOOKS, BIN = H("~/company"), H("~/books"), H("~/books/bin")
QUEUE, PENDING, REPORT = f"{COMPANY}/queue", f"{COMPANY}/decisions/pending.md", f"{COMPANY}/reports/factory.md"
SPEND = f"{COMPANY}/spend.jsonl"
BOOK_CAP, MONTH_CAP = 2.0, 10.0  # MONTH_CAP in USD, recalculated in main() from MONTH_CAP_EUR
MONTH_CAP_EUR = 10.0  # Cleiton's rule, 23 Nov 2026: SPEND cap per month; at the cap it asks whether to go on
USD_CAP_BY_MONTH = {"2026-12": 30.0}  # Cleiton, 25 Nov 2026: December with 1 book per day until 23 Dec, cap US$ 30
MAX_BRIEFS_WAITING = 3  # no book of the day if 3 books of the day already wait at the brief gate
# Pricing rule (decision 0012). The board changes it in ~/company/config.json.
# us_withholding: KDP withholds 30% at source without a W-8BEN; the US-Spain treaty art. 12 limits it to 5% (literary/artistic copyright).
#   Whether KDP applies 5% to coloring books: NOT VERIFIED.
# estimated_irpf: IRPF in Spain falls on profit (sales minus expenses), not on each sale. Marginal rate NOT VERIFIED (accountant).
US_WITHHOLDING, ESTIMATED_IRPF = 0.05, 0.30
LESSONS, IMPROVEMENTS, CONFIG = f"{COMPANY}/lessons.md", f"{COMPANY}/improvements.md", f"{COMPANY}/config.json"  # lessons in the brain (git) since 23 Nov 2026
IMG_COST, COVER_COST, APIFY_COST_PER_BOOK = 0.0065, 0.06, 0.006  # IMG_COST: OpenAI invoice 25 Nov 2026 (US$ 1.10 / ~175 images), approved by Cleiton 25 Nov (rule 0016)
ENV = dict(os.environ, PATH=f"/opt/homebrew/bin:{H('~/.local/bin')}:/usr/bin:/bin:/usr/sbin:/sbin")
PY = sys.executable
today = lambda: datetime.date.today().isoformat()
pending, report_rows = [], []


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def lj(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d


def sj(p, d):
    with open(p, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def spend(desc, usd):
    with open(SPEND, "a") as f:
        f.write(json.dumps({"date": today(), "desc": desc, "usd": round(usd, 4)}, ensure_ascii=False) + "\n")


def apify_wait(cost):
    """Watchdog rule (Cleiton, 23 Nov 2026): no Apify balance is not an error. The task waits for the cycle reset.
    Returns the reason (text) if there is no balance for `cost`, otherwise None. Never prints the key."""
    import urllib.request
    try:
        k = open(os.path.expanduser("~/.apify-personal")).read().strip()
        req = urllib.request.Request("https://api.apify.com/v2/users/me/limits", headers={"Authorization": "Bearer " + k})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)["data"]
        used, maximum = d["current"]["monthlyUsageUsd"], d["limits"]["maxMonthlyUsageUsd"]
        if used + cost > maximum:
            end = d["monthlyUsageCycle"]["endAt"][:10]
            return f"Apify out of balance: US$ {used:.2f} of {maximum:.2f}; cycle ends {end} (UTC)"
    except Exception as e:
        log("apify", "could not read the balance, continuing", str(e)[:200])
    return None


def month_spend():
    m = today()[:7]
    tot = 0.0
    if os.path.exists(SPEND):
        for l in open(SPEND):
            r = json.loads(l)
            if r["date"].startswith(m):
                tot += r["usd"]
    return tot


def usd_per_eur():
    """ECB reference rate (1 EUR = x USD), once a day, saved in ~/company/exchange_rate.json.
    Without a rate: uses the last saved one; without any, 1.0 (lower cap, safe side)."""
    c = lj(f"{COMPANY}/exchange_rate.json", {}) or {}
    if c.get("date") == today():
        return c["usd_per_eur"]
    try:
        import re, urllib.request
        x = urllib.request.urlopen("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=20).read().decode()
        v = float(re.search(r"currency='USD' rate='([0-9.]+)'", x).group(1))
        sj(f"{COMPANY}/exchange_rate.json", {"date": today(), "usd_per_eur": v, "source": "ECB eurofxref-daily"})
        return v
    except Exception:
        return c.get("usd_per_eur", 1.0)


def cap_txt():
    if USD_CAP_BY_MONTH.get(today()[:7]):
        return f"US$ {MONTH_CAP:.2f} (special cap for this month)"
    return f"EUR {MONTH_CAP_EUR:.0f} = US$ {MONTH_CAP:.2f}"


def company_approvals():
    return lj(f"{COMPANY}/approvals.json", {}) or {}


def run(cmd, cwd=None, timeout=None, extra=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                          env=dict(ENV, **(extra or {})), stdin=subprocess.DEVNULL)


def soul(name):
    """Bot soul: first the OpenMausBot one, otherwise ~/books/souls/<Name>.md (factory-only bots)."""
    for b in lj(H("~/.openmausbot/bots.json"), []):
        if b.get("name") == name and b.get("soul"):
            return b["soul"]
    f = f"{BOOKS}/souls/{name}.md"
    return open(f).read().strip() if os.path.exists(f) else ""


def codex(role, request, schema, cwd, out, images=()):
    """Calls the bot (Codex CLI, subscription) in read-only mode and returns the JSON validated by the schema."""
    f_schema = out + ".schema.json"
    sj(f_schema, schema)
    text = (soul(role) + "\n\n" if soul(role) else f"You are the {role}.\n\n") + request + \
        "\nDo not run commands that change files. Answer only with the requested JSON."
    img = [a for f in images for a in ("-i", f)]
    r = run(["codex", "exec", "--skip-git-repo-check", "-s", "read-only"] + img + ["--output-schema", f_schema,
             "-o", out, text], cwd=cwd, timeout=1500)
    d = lj(out)
    if d is None:
        d = gemini_fallback(role, text, f_schema, cwd, out, images, r.stderr[-400:])
    if d is None:
        raise RuntimeError(f"{role} failed: {r.stderr[-400:]}")
    return d


def gemini_fallback(role, text, f_schema, cwd, out, images, codex_error):
    """Decision 0005 (23 Nov 2026): if Codex fails (quota or other error), the same request goes to free Gemini.
    Only public factory data; zero cost, not recorded in the spend log."""
    venv, gj_script = os.path.expanduser("~/.venv-genai/bin/python"), f"{BIN}/gemini_json.py"
    if not (os.path.exists(venv) and os.path.exists(gj_script) and os.path.exists(os.path.expanduser("~/.gemini-personal"))):
        return None
    log(role, "codex failed, using the gemini fallback:", codex_error.strip().replace("\n", " ")[-200:])
    f_req = out + ".request.txt"
    open(f_req, "w").write(text)
    img = [a for f in images for a in ("--img", f)]
    r = run([venv, "-I", "-W", "ignore", gj_script, "--request", f_req, "--schema", f_schema, "--output", out, "--cwd", cwd] + img,
            cwd="/tmp", timeout=600)
    d = lj(out)
    log(role, "gemini fallback", "ok " + r.stdout.strip()[-200:] if d is not None else "failed: " + r.stderr.strip()[-300:])
    return d


def serpapi_fallback(name, kws, n, reason):
    """Amazon data fallback (Cleiton, 24 Nov 2026): with no Apify balance, tries free SerpApi (250/month, fixed limit).
    At most 12 books per keyword, to save searches. Returns the script info or None (then it waits)."""
    if not os.path.exists(os.path.expanduser("~/.serpapi")):
        return None
    log(name, "apify out of balance, using the serpapi fallback:", reason)
    r = run([PY, f"{BIN}/market_serpapi.py"] + list(kws), timeout=2400, extra={"BOOKS_PER_KW": str(min(n, 12))})
    last = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode:
        log(name, "serpapi fallback failed", (last + " " + r.stderr.strip())[-300:])
        return None
    log(name, "serpapi fallback ok", last[-200:])
    return json.loads(last)


def gate(task, key, text, files=()):
    pending.append({"task": task, "decision": key, "text": text, "files": list(files)})


# ----------------------------------------------------------------- book
SCHEMA_BRIEF = {"type": "object", "additionalProperties": False,
                "required": ["title", "subtitle", "cover", "themes", "reuse", "rationale"],
                "properties": {
                    "title": {"type": "string"}, "subtitle": {"type": "string"}, "rationale": {"type": "string"},
                    "themes": {"type": "array", "items": {"type": "string"}},
                    "reuse": {"type": "array", "items": {"type": "string"}},
                    "cover": {"type": "object", "additionalProperties": False,
                              "required": ["title1", "title2", "sub", "back_title", "back_subtitle", "blurb", "bullets", "spine", "scene"],
                              "properties": {k: {"type": "string"} for k in
                                             ["title1", "title2", "back_title", "back_subtitle", "blurb", "spine", "scene"]} |
                              {"sub": {"type": "array", "items": {"type": "string"}},
                               "bullets": {"type": "array", "items": {"type": "string"}}}}}}

SCHEMA_LISTING = {"type": "object", "additionalProperties": False,
                  "required": ["title", "subtitle", "description", "keywords", "categories", "price_usd", "price_eur",
                               "ai_disclosure", "notes"],
                  "properties": {"title": {"type": "string"}, "subtitle": {"type": "string"},
                                 "description": {"type": "string"}, "notes": {"type": "string"},
                                 "keywords": {"type": "array", "items": {"type": "string"}},
                                 "categories": {"type": "array", "items": {"type": "string"}},
                                 "price_usd": {"type": "number"}, "price_eur": {"type": "number"},
                                 "ai_disclosure": {"type": "string"}}}

COPYRIGHT = ["Copyright {year} {brand}. All rights reserved.",
             "Tip: place a sheet of paper behind the page you are coloring. Every design is printed on its own page."]


ARCHIVE = H("~/Finished-Books")
SCHEMA_REVIEW = {"type": "object", "additionalProperties": False,
                 "required": ["approved", "score", "pages_to_redo", "general_problems", "summary"],
                 "properties": {"approved": {"type": "boolean"}, "score": {"type": "integer"}, "summary": {"type": "string"},
                                "general_problems": {"type": "array", "items": {"type": "string"}},
                                "pages_to_redo": {"type": "array", "items": {
                                    "type": "object", "additionalProperties": False, "required": ["id", "reason"],
                                    "properties": {"id": {"type": "string"}, "reason": {"type": "string"}}}}}}


SCHEMA_STOREFRONT = {"type": "object", "additionalProperties": False, "required": ["candidates", "choice", "rationale"],
                     "properties": {"choice": {"type": "string"}, "rationale": {"type": "string"},
                                    "candidates": {"type": "array", "items": {
                                        "type": "object", "additionalProperties": False,
                                        "required": ["id", "storefront_score", "title_covers_face", "scene_matches_title", "problems"],
                                        "properties": {"id": {"type": "string"}, "storefront_score": {"type": "integer"},
                                                       "title_covers_face": {"type": "boolean"},
                                                       "scene_matches_title": {"type": "boolean"},
                                                       "problems": {"type": "array", "items": {"type": "string"}}}}}}}


def storefront(folder, L, fronts):
    """Cleiton, 25 Nov 2026: the cover must make someone scrolling search results stop and click.
    Lays out the candidate fronts as thumbnails next to the competitor covers the benchmark saw and asks for the choice."""
    from PIL import Image, ImageDraw
    comp = sorted(glob.glob(f"{folder}/benchmark/img/cover-*.jpg"))[:8] + sorted(glob.glob(f"{folder}/benchmark/img-stores/*-1.jpg"))[:4]
    def row(items, side):
        sheet = Image.new("RGB", (len(items) * (side + 16) + 16, side + 40), "white"); d = ImageDraw.Draw(sheet)
        for i, (label, fi) in enumerate(items):
            t = Image.open(fi).convert("RGB"); t.thumbnail((side, side)); x = 16 + i * (side + 16)
            d.text((x, 6), label, fill="black"); sheet.paste(t, (x, 26))
        return sheet
    ours = [(k, fr) for k, fr in fronts]
    parts = [row(ours, 420), row(ours + [(f"competitor {i + 1}", c) for i, c in enumerate(comp)], 130)]
    out = Image.new("RGB", (max(p.width for p in parts), sum(p.height for p in parts) + 20), "white")
    y = 0
    for p in parts:
        out.paste(p, (0, y)); y += p.height + 20
    sheet_f = f"{folder}/kit/storefront.png"
    out.save(sheet_f)
    v = codex("Revisor", (
        "You judge book covers the way a shopper scrolls search results for "
        f"'{L['title']}'-type adult coloring books. The attached sheet shows our candidate front covers "
        f"({', '.join(k for k, _ in ours)}) large on top, and below the same candidates at search-result thumbnail size "
        + (f"next to {len(comp)} competitor covers. " if comp else "(no competitor covers available). ")
        + f"Our title: {L['cover'].get('title1', '')} {L['cover'].get('title2', '')}. The book: {L['subtitle']}.\n"
        "For each candidate give storefront_score 0-10: would it make a shopper stop and click among the competitors at "
        "thumbnail size (strong saturated color, big readable title, clear focal subject with faces, matches what the book "
        "promises). title_covers_face=true if the title or subtitle hides any part of a person's or animal's head: look at the large versions, right behind and just under the title letters; a body or legs whose head is not visible counts as a hidden head. scene_matches_title=false if the "
        "scene contradicts the title. problems: concrete visible defects only (deformed hands or faces, cut-off heads, "
        "text inside the art). choice = id of the best candidate with no covered face and a matching scene. "
        "Write rationale in English, 2-4 short sentences comparing with the competitors."),
        SCHEMA_STOREFRONT, folder, f"{folder}/kit/storefront.json", [sheet_f])
    return v


def contact_sheets(folder, L, st, per=12, side=420):
    """Contact sheets with all approved pages, labelled by id, so the reviewer sees the whole book."""
    from PIL import Image, ImageDraw
    ok = [(p["id"], f"{folder}/final/{p['id']}.png") for p in L["pages"] if st.get(p["id"], {}).get("state") == "approved"]
    os.makedirs(f"{folder}/kit/review", exist_ok=True)
    outs = []
    for i in range(0, len(ok), per):
        batch = ok[i:i + per]
        sheet = Image.new("RGB", (4 * (side + 10) + 10, 3 * (side + 40) + 10), "white")
        d = ImageDraw.Draw(sheet)
        for j, (pid, f) in enumerate(batch):
            im = Image.open(f).convert("RGB"); im.thumbnail((side, side))
            x, y = 10 + (j % 4) * (side + 10), 10 + (j // 4) * (side + 40)
            d.text((x, y), pid, fill="black"); sheet.paste(im, (x, y + 25)); d.rectangle([x, y + 25, x + side - 1, y + 25 + side - 1], outline=(180, 180, 180))
        outs.append(f"{folder}/kit/review/sheet-{i // per + 1}.png"); sheet.save(outs[-1])
    return outs


def checks(folder, L, st):
    """Checks that do not need eyes: counts, safe zone, near-identical pages."""
    from PIL import Image
    errors = []
    approved = [p["id"] for p in L["pages"] if st.get(p["id"], {}).get("state") == "approved"]
    if len(approved) != len(L["pages"]):
        errors.append(f"{len(L['pages']) - len(approved)} pages without approval")
    nums = {int(w) for w in " ".join(L["cover"].get("sub", [])).split() if w.isdigit()}
    if nums and nums != {len(approved)}:
        errors.append(f"the cover promises {sorted(nums)} designs and the book has {len(approved)}")
    if not lj(f"{folder}/kit/cover.json", {}).get("title_inside_safe_zone"):
        errors.append("cover title outside the safe zone")
    if lj(f"{folder}/kit/interior.json", {}).get("interior_pages", 0) < 24:
        errors.append("interior with fewer than 24 pages")
    hs = {}
    for pid in approved:
        im = Image.open(f"{folder}/final/{pid}.png").convert("L").resize((9, 8))
        px_ = list(im.getdata())
        hs[pid] = [px_[r * 9 + c] > px_[r * 9 + c + 1] for r in range(8) for c in range(8)]
    similar = [f"{a} and {b}" for i, a in enumerate(approved) for b in approved[i + 1:]
               if sum(x != y for x, y in zip(hs[a], hs[b])) <= 6]
    return errors, similar


SCHEMA_CONFIRM = {"type": "object", "additionalProperties": False, "required": ["confirmed", "evidence"],
                  "properties": {"confirmed": {"type": "boolean"}, "evidence": {"type": "string"}}}


def confirm(folder, pid, theme, reason):
    """Second look: does the defect flagged on the contact sheet really exist on the full-size page?
    Calibrated 2026-11-22: in the 1st real review, 7 of 8 flagged defects did not exist."""
    from PIL import Image
    img = f"{folder}/kit/review/{pid}.png"
    Image.open(f"{folder}/final/{pid}.png").convert("L").resize((1024, 1024)).save(img)
    d = codex("Verificador", (
        "You check one claimed defect on one page of an adult coloring book. Look only at the attached page.\n"
        f"Page theme: {theme}\nClaimed defect: {reason}\n"
        "Set confirmed=true only if the defect is clearly and literally visible and would bother a buyer. "
        "Readable letters or digits count as text; hearts, dots, chocolate chips, stripes, a blank music stand or "
        "blank book spines do not. A pose or action of a character or animal that differs from the theme is NOT a "
        "defect. Small style differences of a recurring character between pages are NOT a defect. If you are not sure, confirmed=false. "
        "In evidence, say in English exactly where you see it, or why it is not there."),
        SCHEMA_CONFIRM, folder, f"{folder}/kit/review/{pid}.conf.json", [img])
    return d


def slug(t):
    return "".join(c if c.isalnum() else "-" for c in t.lower()).strip("-").replace("--", "-")


def book_cost(folder):
    st = lj(f"{folder}/state.json", {})
    n = sum(len(s.get("attempts", [])) + len(s.get("history", [])) for s in st.values())
    return n * IMG_COST + len(glob.glob(f"{folder}/kit/cover-art*.png")) * COVER_COST

# ----------------------------------------------------------------- price (decision 0012)
def kdp_print_cost(pages):
    """Amazon.com, black ink, large trim (8.5x8.5). Official source: kdp.amazon.com/help/topic/G201834340, read 2026-11-22."""
    return 2.84 if pages <= 110 else 1.00 + 0.017 * pages


def net_per_sale(channel, p, pages=0):
    """What arrives per sale after the platform (and the US withholding on KDP), before IRPF."""
    if channel == "kdp":  # royalty 60% from 9.99, 50% below, minus printing (G201834340); US withholding at source
        wh = lj(CONFIG, {}).get("us_withholding", US_WITHHOLDING)
        return ((0.6 if p >= 9.99 else 0.5) * p - kdp_print_cost(pages)) * (1 - wh)
    return p - (0.10 * p + 0.50) - (0.029 * p + 0.30)  # Gumroad: 10% + 0.50 and card 2.9% + 0.30 (help article 66)


def estimated_creation_cost(n_pages):
    """Cost of creating a book (images, cover, Apify), paid once. Average of books already made; without history, estimates."""
    done = [m["recorded_spend_usd"] for m in (lj(f) for f in glob.glob(f"{BOOKS}/*/kit/metrics.json")) if m]
    return round(max(statistics.mean(done) if done else 0, n_pages * 1.5 * IMG_COST + 3 * COVER_COST), 2)


def price_below(channel, median, pages=0, creation_cost=0.0):
    """Rule 0012: the highest price ending in .49 or .99 below the median of the competitors that sell, as long as the
    FIRST sale pays the book's creation cost. IRPF falls on profit and the creation cost is deductible, so the
    first sale (zero profit) pays no IRPF; the following ones do (profit_after_irpf). If nothing below the median pays the
    cost, returns ok=False and the minimum price that pays."""
    cfg = lj(CONFIG, {})
    irpf = cfg.get("estimated_irpf", ESTIMATED_IRPF)
    floor = round(max(cfg.get("net_floor", 0), creation_cost), 2)
    def row(p):
        net = net_per_sale(channel, p, pages)
        return {"price": p, "net_per_sale": round(net, 2), "profit_after_irpf": round(net * (1 - irpf), 2),
                "ok": net >= floor}
    steps = sorted({round(math.floor(median) - k + d, 2) for k in range(12) for d in (0.49, 0.99)}, reverse=True)
    below = [x for x in steps if 0 < x < median]
    alts = [row(x) for x in below[:6]]
    above = sorted({round(math.floor(median) + k + d, 2) for k in range(0, 20) for d in (-0.51, -0.01, 0.49, 0.99)})
    minimum = next((row(x) for x in above if x > 0 and row(x)["ok"]), None)
    return {"channel": channel, "competitor_median": median, "estimated_irpf": irpf, "creation_cost": floor,
            "pages": pages, **(alts[0] if alts else {"price": None, "ok": False}), "alternatives": alts,
            "min_price_that_pays": minimum}


# ----------------------------------------------------------------- benchmark (decision 0012)
SCHEMA_BENCH = {"type": "object", "additionalProperties": False,
                "required": ["use_character", "character", "character_rationale", "page_style", "cover_direction",
                             "selling_themes", "complaints", "praise", "do_better", "report_md", "confidence"],
                "properties": {"use_character": {"type": "boolean"}, "character": {"type": "string"},
                               "character_rationale": {"type": "string"}, "page_style": {"type": "string"},
                               "cover_direction": {"type": "string"}, "report_md": {"type": "string"},
                               "confidence": {"type": "integer"}} |
                              {k: {"type": "array", "items": {"type": "string"}}
                               for k in ["selling_themes", "complaints", "praise", "do_better"]}}

# Rules that hold in any niche (learned in book 1): the benchmark picks the style, the code appends this.
PAGE_RULES = ("Draw the whole scene as one complete vignette centered on the page with a wide white margin on every "
              "side; nothing touches or is cut by the page edges. Avoid hanging signs, labels, posters, book titles and "
              "anything that could carry writing. Black outlines on a pure white background, no shading, no hatching, "
              "no gray, no color, no text, no letters, no numbers. No border, no frame, no arch or outline enclosing the scene "
              "or the page.")


def lessons():
    return open(LESSONS).read()[-3000:] if os.path.exists(LESSONS) else "(no lessons yet)"


def _attr(it, *keys):
    return next((a.get("value") for a in it.get("attributes") or [] if a.get("key") in keys), None)


def is_coloring(t):
    t = (t or "").lower()
    if "coloring" not in t and "colouring" not in t:
        return False
    if "kids" in t and "adult" not in t:
        return False
    return not any(w in t for w in ["puzzle", "sticker", "calendar", "planner", "journal", "word search", "activity book"])


def competitor_sheets(bd, books):
    """Only with board authorisation (config benchmark_amazon_images): covers and sample pages of the best sellers."""
    import urllib.request
    from PIL import Image, ImageDraw
    os.makedirs(f"{bd}/img", exist_ok=True)
    def fetch(url, f):
        if not os.path.exists(f):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            open(f, "wb").write(urllib.request.urlopen(req, timeout=30).read())
        return f
    covers = [(f"{i + 1}", fetch(x["cover"], f"{bd}/img/cover-{i + 1}.jpg")) for i, x in enumerate(books[:12]) if x.get("cover")]
    inter = [(f"{i + 1}.{j + 1}", fetch(u, f"{bd}/img/int-{i + 1}-{j + 1}.jpg"))
             for i, x in enumerate(books[:6]) for j, u in enumerate(x.get("gallery", [])[:2])]
    outs = []
    for fname, batch in (("covers", covers), ("interiors", inter)):
        if not batch:
            continue
        side = 400
        sheet = Image.new("RGB", (4 * (side + 10) + 10, ((len(batch) + 3) // 4) * (side + 40) + 10), "white")
        d = ImageDraw.Draw(sheet)
        for j, (label, f) in enumerate(batch):
            im = Image.open(f).convert("RGB"); im.thumbnail((side, side))
            x, y = 10 + (j % 4) * (side + 10), 10 + (j // 4) * (side + 40)
            d.text((x, y), label, fill="black"); sheet.paste(im, (x, y + 25))
        outs.append(f"{bd}/sheet-{fname}.png"); sheet.save(outs[-1])
    return outs


def benchmark(name, folder, req, n_pages, ap):
    """Step 0 (decision 0012): before the brief, see what the competition does (covers, drawings, price) to do better."""
    bf, bd = f"{folder}/benchmark.json", f"{folder}/benchmark"
    if os.path.exists(bf):
        return lj(bf)
    os.makedirs(bd, exist_ok=True)
    source = H(req["market_data"]) if req.get("market_data") else None
    if not source:  # no recent collection: calls the Apify actor (decision 0008)
        kws = req.get("keywords") or []
        if not kws:
            raise RuntimeError("request without keywords or market_data for the benchmark")
        n = int(req.get("books_per_kw", 36))
        cost = len(kws) * n * APIFY_COST_PER_BOOK
        if month_spend() + cost > MONTH_CAP and not (ap.get("month_cap_" + today()[:7]) or company_approvals().get("month_cap_" + today()[:7])):
            gate(name, "month_cap_" + today()[:7], f"Benchmark would cost ~US$ {cost:.2f}; the month would go above the cap {cap_txt()}.")
            return "gate"
        short = apify_wait(cost)
        if short:
            info = serpapi_fallback(name, kws, n, short)
            if not info:
                log(name, "benchmark waiting", short)
                return "waiting"
        else:
            log(name, "benchmark apify", kws)
            r = run([PY, f"{BIN}/market_amazon2.py"] + kws, timeout=2400, extra={"BOOKS_PER_KW": str(n)})
            if r.returncode:
                raise RuntimeError("apify: " + (r.stdout + r.stderr)[-400:])
            info = json.loads(r.stdout.strip().splitlines()[-1])
            spend(f"{name}: benchmark apify", info.get("cost_usd") or cost)
        source = info["file"]
    seen, books = set(), []
    for it in lj(source)["items"]:
        if it.get("asin") in seen or not is_coloring(it.get("title")) or not (it.get("price") or {}).get("value"):
            continue
        seen.add(it.get("asin"))
        date = _attr(it, "Publication date")
        try:
            date = datetime.datetime.strptime(date, "%B %d, %Y").date().isoformat()
        except Exception:
            pass
        books.append({"title": it["title"], "author": it.get("author"), "price": it["price"]["value"],
                      "reviews": it.get("reviewsCount") or 0, "stars": it.get("stars"),
                      "bsr": next((r["rank"] for r in it.get("bestsellerRanks") or [] if r.get("category") == "Books"), None),
                      "published": date, "pages": _attr(it, "Print length", "Paperback"),
                      "review_summary": (it.get("aiReviewsSummary") or {}).get("text"),
                      "description": str(it.get("bookDescription") or it.get("description") or "")[:600],
                      "cover": it.get("thumbnailImage"), "gallery": (it.get("highResolutionImages") or [])[1:4]})
    books.sort(key=lambda x: x["bsr"] or 10 ** 9)
    selling = [x for x in books if x["bsr"] and x["bsr"] < 100000]
    if len(selling) < 5:
        raise RuntimeError(f"benchmark: only {len(selling)} coloring books with BSR < 100k")
    prices = {"amazon": {"median": round(statistics.median(x["price"] for x in selling), 2), "n": len(selling),
                         "source": source, "note": "coloring books with BSR < 100k on Amazon.com, one-day snapshot"}}
    if req.get("gumroad_query"):
        r = run(["gumroad", "products", "comps", "--query", req["gumroad_query"], "--json"], timeout=120)
        try:
            c = json.loads(r.stdout)["comps"]
            prices["gumroad"] = {"median": c["price_cents"]["p50"] / 100, "p25": c["price_cents"]["p25"] / 100,
                                 "p75": c["price_cents"]["p75"] / 100, "n": c["count"], "query": req["gumroad_query"],
                                 "note": "Gumroad comps: all paid products that match the search (includes bundles)"}
        except Exception:
            log(name, "gumroad comps failed", r.stderr[-200:])
    sj(f"{bd}/data.json", {"books": books[:40], "prices": prices})
    imgs = competitor_sheets(bd, selling) if lj(CONFIG, {}).get("benchmark_amazon_images") else []
    n_amazon = len(imgs)
    # Cleiton, 25 Nov 2026 (decision 0021): look at the drawings in the competitors' own stores, only where robots.txt allows
    store_domains, store_notes = lj(CONFIG, {}).get("competitor_stores") or [], []
    if store_domains:
        sys.path.insert(0, BIN)
        import stores
        q_store = req.get("store_query") or req.get("gumroad_query") or (req.get("keywords") or [""])[0]
        try:
            f_s, store_notes = stores.sheet(bd, q_store, store_domains)
        except Exception as e:
            f_s, store_notes = [], [f"stores failed: {type(e).__name__}: {e}"]
        imgs += f_s
        log(name, "benchmark stores", "; ".join(store_notes))
    log(name, "benchmark analyst", len(books), "books", len(imgs), "sheets")
    a = codex("Analista", (
        f"Competitor benchmark before we make a coloring book. Board request: {json.dumps(req, ensure_ascii=False)}.\n"
        "Data: the file benchmark/data.json in this folder (Amazon.com coloring books sorted by BSR: price, "
        "reviews, stars, publication date, pages, review summary, description). Read it.\n"
        + (("The attached images: " + ("first the covers (numbered in file order) and sample pages "
            "(book.sample) of the best sellers on Amazon; " if n_amazon else "")
            + ("sheet-stores.png has product photos taken from the competitors' own stores (" + ", ".join(store_domains)
               + "), with pages from inside the books; they are marketing photos (open book, background, badges), judge only the "
                 "drawings: line weight, amount of detail, people and faces, frames. " if len(imgs) > n_amazon else "")
            + "Look at them and say in the report what you saw. ") if imgs else
           "You have no images: judge covers and drawings only from what titles, descriptions and reviews say, and write that "
           "in the report. ")
        + f"Lessons from previous books:\n{lessons()}\n"
        "Answer:\n(1) use_character: do the best sellers in this niche use a recurring character (e.g. the same cat on "
        "every page)? Only true if the data shows it helps here. character = fixed description in English, with size, body shape, markings and face, "
        "to use with the same text on every page (empty if false). character_rationale with the evidence.\n(2) page_style: prompt in English to generate each page, with "
        "{theme} where the theme goes; state the level of detail and the line style this niche asks for (bold and easy, detailed, etc.) "
        "and the character if use_character. No rules about margins, text or color: the code appends them.\n(3) cover_direction: in "
        "English, how the full-color illustration on our cover stands out from the covers that sell.\n(4) selling_themes; complaints and "
        "praise that repeat in the reviews; do_better = what we do to beat the best ones.\n"
        "You do not decide the price (the code calculates it). Separate measured facts from estimates. Never invent numbers. "
        "report_md in English, short, with a table of the 10 best sellers. confidence 0-100."),
        SCHEMA_BENCH, folder, f"{bd}/analysis.json", imgs)
    if "{theme}" not in a["page_style"]:
        raise RuntimeError("benchmark: page_style without {theme}")
    b = dict(a, prices=prices, images=bool(imgs), date=today())
    sj(bf, b)
    est_pages = 2 * n_pages + 2
    lines = [f"# Benchmark: {req.get('niche', '')[:80]}", "", f"{today()}. Confidence {a['confidence']}%. "
             f"Competitor images seen: {'yes' if imgs else 'no (text only)'}.", ""] + \
            (["## Images from the competitors' stores (only where robots.txt allows; never Amazon, Etsy, Gumroad)", ""]
             + [f"- {x}" for x in store_notes] + [""] if store_notes else []) + [
             "## Price (rule 0012: below the median, with a floor after fees and tax reserve)",
             "", "| Channel | Competitor median | Our price | Net per sale | Profit per sale after IRPF (2nd sale onwards) | 1st sale pays creation | Minimum price that pays |", "|---|---|---|---|---|---|---|"]
    for channel, k in (("kdp", "amazon"), ("gumroad", "gumroad")):
        if k in prices:
            pr = price_below(channel, prices[k]["median"], est_pages if channel == "kdp" else 0, estimated_creation_cost(n_pages))
            lines += [f"| {channel} | {pr['competitor_median']} ({prices[k]['n']} products) | {pr['price']} | "
                      f"{pr['net_per_sale']} | {pr['profit_after_irpf']} | {'yes' if pr['ok'] else 'NO'} (US$ {pr['creation_cost']}) | "
                      f"{(pr['min_price_that_pays'] or {}).get('price', '-')} |"]
    lines += ["", f"Estimated IRPF {int(lj(CONFIG, {}).get('estimated_irpf', ESTIMATED_IRPF) * 100)}% on profit and US withholding "
              "5% on KDP: NOT VERIFIED, confirm with the accountant. KDP estimated with ~" + str(est_pages) + " pages; the final price comes out in the listing.",
              "", "## Character", f"{'Yes: ' + a['character'] if a['use_character'] else 'No.'} {a['character_rationale']}",
              "", "## Do better"] + [f"- {x}" for x in a["do_better"]] + \
             ["", "## Cover", a["cover_direction"], "", "## Page style", a["page_style"], "", a["report_md"]]
    open(f"{folder}/BENCHMARK.md", "w").write("\n".join(lines) + "\n")
    return b


# ----------------------------------------------------------------- retro (decision 0012)
SCHEMA_RETRO = {"type": "object", "additionalProperties": False,
                "required": ["went_well", "went_badly", "stop", "improve", "lessons", "summary"],
                "properties": {"summary": {"type": "string"},
                               "improve": {"type": "array", "items": {
                                   "type": "object", "additionalProperties": False,
                                   "required": ["action", "evidence", "expected_gain", "type"],
                                   "properties": {"action": {"type": "string"}, "evidence": {"type": "string"},
                                                  "expected_gain": {"type": "string"},
                                                  "type": {"type": "string", "enum": ["cost", "quality", "time"]}}}}} |
                              {k: {"type": "array", "items": {"type": "string"}}
                               for k in ["went_well", "went_badly", "stop", "lessons"]}}


def metrics(folder, L, st, rv):
    from collections import Counter
    pgs = [st.get(p["id"], {}) for p in L["pages"]]
    att = [tt for s in pgs for tt in s.get("history", []) + s.get("attempts", [])]
    approved = sum(1 for s in pgs if s.get("state") == "approved")
    first = sum(1 for s in pgs if s.get("state") == "approved" and len(s.get("attempts", [])) == 1
                and not s.get("history"))
    reasons = Counter()
    for tt in att:
        r = tt.get("reviewer") or {}
        if not r.get("approved"):
            for m in (r.get("defects") or []) + (r.get("problems") or []):
                reasons[str(m)[:140]] += 1
    base = os.path.basename(folder)
    spends = [json.loads(l) for l in open(SPEND)] if os.path.exists(SPEND) else []
    spent = round(sum(g["usd"] for g in spends if base in g["desc"]), 2)
    return {"book": L.get("title"), "pages": len(pgs), "approved_count": approved, "images_generated": len(att),
            "images_per_page": round(len(att) / max(approved, 1), 2),
            "approved_first_try_pct": round(100 * first / max(len(pgs), 1)),
            "rejections_by_reason_top10": reasons.most_common(10),
            "redone_by_final_review": sum(1 for s in pgs if s.get("review_corrections")),
            "final_review": {"score": rv.get("score"), "flagged": len(rv.get("flagged", [])),
                             "confirmed": len(rv.get("pages_to_redo", [])), "discarded": len(rv.get("discarded", []))},
            "recorded_spend_usd": spent, "estimated_image_cost_usd": round(book_cost(folder), 2),
            "cost_per_approved_page_usd": round(spent / max(approved, 1), 3),
            "cost_note": "codex (subscription) costs 0 per call; only images and Apify count as spend",
            "had_benchmark": os.path.exists(f"{folder}/benchmark.json")}


DRIVE_BOOKS_FOLDER = (lj(CONFIG, {}) or {}).get("drive_books_folder", "")  # personal Drive: books folder (config.json)
RCLONE = H("~/.local/bin/rclone")


def drive_and_spreadsheet(name, folder, L, dest):
    """Step K (Cleiton's request, 22 Nov 2026): uploads the whole book (printable PDF), the 5-page sample and the
    KDP files to the personal Drive and rebuilds the Log Production tab of the spreadsheet. Does not block the book: if it fails (e.g. weekly
    Drive login expired), it tries again on the next round."""
    import subprocess
    kit = f"{folder}/kit"
    py = sys.executable
    if not os.path.exists(f"{kit}/printable.pdf"):
        subprocess.run([py, f"{BIN}/printable.py", folder], check=True, capture_output=True)
    if not os.path.exists(f"{kit}/sample/sample.pdf"):
        subprocess.run([py, f"{BIN}/printable.py", folder, "--sample", "5"], check=True, capture_output=True)
    lst = lj(f"{kit}/listing.json", {})
    if not os.path.exists(f"{kit}/prices.json"):
        pk, pg = lst.get("kdp_price") or {}, lst.get("gumroad_price") or {}
        sj(f"{kit}/prices.json", {
            "kdp": {"median": pk.get("competitor_median"), "source": "book benchmark (BENCHMARK.md)",
                    "price": pk.get("price", lst.get("price_usd")), "state": "proposed (upload pending)"},
            "gumroad": {"median": pg.get("competitor_median"), "source": "book benchmark (BENCHMARK.md)",
                        "price": pg.get("price"), "state": "proposed (draft)"}})
    dr = lj(f"{kit}/drive.json", {}) or {}
    if not dr.get("folder"):
        root = ["--drive-root-folder-id", DRIVE_BOOKS_FOLDER]
        r = subprocess.run([RCLONE, "lsf", "personal:", "--dirs-only"] + root, capture_output=True, text=True, timeout=120)
        if r.returncode:
            raise RuntimeError("rclone has no access to Drive (weekly login?): " + r.stderr[-200:])
        nums = [int(x[:2]) for x in r.stdout.splitlines() if x[:2].isdigit() and x[2:3] == " "]
        t = lst.get("title") or L.get("title") or name
        d = f"personal:{(max(nums) + 1 if nums else 1):02d} {t}"
        uploads = [(f"{kit}/printable.pdf", f"{d}/{t} - Full Book (printable, US Letter).pdf"),
                   (f"{kit}/sample/sample.pdf", f"{d}/{t} - Free Sample (5 pages).pdf"),
                   (f"{kit}/interior.pdf", f"{d}/KDP files/{t} - KDP Interior.pdf"),
                   (f"{kit}/cover.pdf", f"{d}/KDP files/{t} - KDP Cover.pdf")]
        for a, b in uploads:
            subprocess.run([RCLONE, "copyto", a, b] + root, check=True, capture_output=True, timeout=900)
        js = json.loads(subprocess.run([RCLONE, "lsjson", d, "-R"] + root, check=True, capture_output=True, text=True).stdout)
        pid = json.loads(subprocess.run([RCLONE, "lsjson", "personal:", "--dirs-only"] + root, check=True,
                                        capture_output=True, text=True).stdout)
        dr = {"folder": next(x["ID"] for x in pid if x["Name"] == d.split(":", 1)[1]),
              "sample": next((x["ID"] for x in js if "Free Sample" in x["Name"]), ""),
              "state": "Kit ready: KDP upload pending (Cleiton)"}
        sj(f"{kit}/drive.json", dr)
        log(name, "drive", d)
    subprocess.run([py, f"{BIN}/spreadsheet.py"], check=True, capture_output=True, timeout=300)
    log(name, "spreadsheet", "Log Production tab updated")


def retro(name, folder, L, st, rv):
    """Sprint review at the end of each book (decision 0012): went well, went badly, stop, improve.
    Code changes stay only as proposals in ~/company/improvements.md; the board approves."""
    m = metrics(folder, L, st, rv)
    sj(f"{folder}/kit/metrics.json", m)
    before = [{"book": x.get("book"), **{k: x.get(k) for k in ("images_per_page", "approved_first_try_pct",
              "cost_per_approved_page_usd", "recorded_spend_usd")}}
              for x in (lj(f) for f in glob.glob(f"{BOOKS}/*/kit/metrics.json") if not f.startswith(folder)) if x]
    log(name, "retro")
    r = codex("Retro", (
        "You run the sprint review of our coloring book assembly line, after finishing this book. Goal: "
        "spend as little as possible to deliver the best book.\n"
        f"Metrics measured by the code: {json.dumps(m, ensure_ascii=False)}\n"
        f"Previous books (to compare): {json.dumps(before, ensure_ascii=False) if before else 'none'}\n"
        "Also read kit/REVIEW.md and, if it exists, BENCHMARK.md in this folder. Lessons we already had:\n" + lessons() + "\n"
        "Answer in English: went_well, went_badly, stop (what we stop doing), improve (concrete actions; each "
        "one with the metric that justifies it, the expected gain in US$ or in quality, and the type), lessons (short rules for "
        "the next benchmarks and briefs, only the new ones) and summary (3-5 sentences). Use only the numbers given; never invent. "
        "Code changes are proposals: the board approves."), SCHEMA_RETRO, folder, f"{folder}/kit/retro.json")
    md = [f"# Sprint review: {L['title']}", "", f"{today()}.", "", r["summary"], "", "## Numbers",
          f"- Approved pages: {m['approved_count']}/{m['pages']}; first try: {m['approved_first_try_pct']}%",
          f"- Images generated: {m['images_generated']} ({m['images_per_page']} per page)",
          f"- Recorded spend: US$ {m['recorded_spend_usd']} (US$ {m['cost_per_approved_page_usd']} per page)",
          f"- Final review: score {m['final_review']['score']}, {m['final_review']['flagged']} flagged, "
          f"{m['final_review']['confirmed']} confirmed"]
    for tit, k in (("Went well", "went_well"), ("Went badly", "went_badly"), ("Stop", "stop"), ("Lessons", "lessons")):
        md += ["", f"## {tit}"] + [f"- {x}" for x in r[k]]
    md += ["", "## Improve"] + [f"- [{x['type']}] {x['action']} (gain: {x['expected_gain']}; why: {x['evidence']})"
                                for x in r["improve"]]
    open(f"{folder}/kit/RETRO.md", "w").write("\n".join(md) + "\n")
    with open(IMPROVEMENTS, "a") as f:
        f.write(f"\n## {today()} {L['title']} (proposals, board approves)\n" +
                "".join(f"- [ ] [{x['type']}] {x['action']} (gain: {x['expected_gain']})\n" for x in r["improve"]))
    with open(LESSONS, "a") as f:
        f.write(f"\n## {L['title']} ({today()})\n" + "".join(f"- {x}\n" for x in r["lessons"]))
    return r


def book(t, name):
    folder = H(t["folder"])
    L = lj(f"{folder}/book.json")
    ap = lj(f"{folder}/approvals.json", {})
    os.makedirs(f"{folder}/kit", exist_ok=True)
    req = L.get("request", {})
    n_pages = int(req.get("pages", 50))

    # 0. competitor benchmark (decision 0012)
    if not L.get("pages"):
        bench = benchmark(name, folder, req, n_pages, ap)
        if bench in ("gate", "waiting"):
            return bench

    # A. brief
    if not L.get("pages"):
        log(name, "brief")
        # Cleiton, 25 Nov 2026 (decision 0024): bank of pages from published books, up to 30% of the new book
        sys.path.insert(0, BIN)
        import image_bank
        bank = {x["key"]: x for x in image_bank.index(exclude=(os.path.basename(folder),))}
        max_reuse = image_bank.maximum(n_pages) if bank and not req.get("no_bank") else 0
        bank_txt = ("" if not max_reuse else
                    f"\nBANK of pages already drawn and approved in our other books (key: theme [book]). You may pick "
                    f"up to {max_reuse} for this book in 'reuse' (the exact keys), ONLY the ones that really fit the angle and the "
                    "audience of this book; zero is also fine. The picked ones count toward the total: new themes + reuse = "
                    f"{n_pages}. The new themes must not repeat the bank scenes you picked.\n"
                    + "\n".join(f"- {k}: {x['theme']} [{x['title']}]" for k, x in bank.items()))
        b = codex("Editor", (
            f"Prepare the brief for an adult coloring book. Board request: {json.dumps(req, ensure_ascii=False)}.\n"
            f"Give: title and subtitle (language of the market), {n_pages} page themes DIFFERENT from each other (each theme a "
            "concrete scene that can be drawn in thick lines, no text, no third-party brands or characters), the cover texts "
            "(title1 = big word of the title, title2 = rest of the book name, at most 3 words and 20 characters, without the words Coloring Book for Adults, sub = 2 short uppercase lines, "
            "back cover texts without health promises, 3 short bullets, spine = title in uppercase, scene = description of the "
            "full-color cover illustration) and a short rationale in English. The number of designs must match "
            f"{n_pages}. Format 8.5x8.5 in, single-sided pages.\n"
            f"Follow the competitor benchmark (BENCHMARK.md in this folder). Recurring character: "
            f"{bench['character'] if bench['use_character'] else 'NONE, do not add a fixed character'}. "
            f"Themes that sell: {'; '.join(bench['selling_themes'])}. Do better: {'; '.join(bench['do_better'])}. "
            f"Cover: {bench['cover_direction']}\nLessons from previous books:\n{lessons()}" + bank_txt), SCHEMA_BRIEF, folder,
            f"{folder}/brief.json")
        reuse = [bank[k] for k in dict.fromkeys(b.get("reuse") or []) if k in bank][:max_reuse]
        if reuse:  # all in the same drawing style, otherwise the book looks mixed
            reuse = [x for x in reuse if x["style"] == reuse[0]["style"]]
        if len(b["themes"]) + len(reuse) < n_pages:
            raise RuntimeError(f"brief with {len(b['themes'])} themes + {len(reuse)} from the bank, requested {n_pages}")
        new = [{"theme": x} for x in b["themes"][:n_pages - len(reuse)]]
        # reused pages spread across the book, not all together
        order, k = list(new), 0
        for j, x in enumerate(reuse):
            pos = round((j + 0.5) * len(new) / len(reuse)) + j
            order.insert(pos, {"theme": x["theme"], "origin": {"book": x["book"], "id": x["id"], "title": x["title"]}})
        L.update(title=b["title"], subtitle=b["subtitle"], cover=b["cover"], size="1024x1024",
                 style=(reuse[0]["style"] if reuse else
                        L["style"] if L.get("fixed_style") else bench["page_style"] + " " + PAGE_RULES),
                 mascot=None if reuse else bench["character"] if bench["use_character"] else None,
                 cover_direction=bench["cover_direction"],
                 pages=[dict(p, id=f"p{i + 1:02d}") for i, p in enumerate(order[:n_pages])])
        sj(f"{folder}/book.json", L)
    if not ap.get("brief") or not L.get("brand") or "[" in L.get("brand", "["):
        n_reused = sum(1 for p in L["pages"] if p.get("origin"))
        gate(name, "brief", f"Approve brief: \"{L['title']}\" ({len(L['pages'])} pages"
             + (f", {n_reused} from the bank of earlier books" if n_reused else "") + "). "
             f"Brand/author: {L.get('brand') or 'NOT DEFINED YET'}.",
             [f"{folder}/BENCHMARK.md", f"{folder}/book.json", f"{folder}/brief.json"])
        return "gate"

    # C. pages
    st = lj(f"{folder}/state.json", {})
    changed = False
    for p in L["pages"]:
        o = p.get("origin")
        if o and st.get(p["id"], {}).get("state") != "approved":
            src = f"{BOOKS}/{o['book']}/final/{o['id']}.png"
            os.makedirs(f"{folder}/final", exist_ok=True)
            shutil.copy(src, f"{folder}/final/{p['id']}.png")
            st[p["id"]] = {"state": "approved", "attempts": [], "reused_from": o}
            changed = True
    if changed:
        sj(f"{folder}/state.json", st)
        log(name, "pages from the bank", sum(1 for p in L["pages"] if p.get("origin")))
    done = [p for p in L["pages"] if st.get(p["id"], {}).get("state") in ("approved", "human_queue")]
    if len(done) < len(L["pages"]):
        missing = (len(L["pages"]) - len(done)) * 1.5 * IMG_COST
        if book_cost(folder) + missing > BOOK_CAP and not ap.get("book_cap"):
            gate(name, "book_cap", f"Pages would cost ~US$ {book_cost(folder) + missing:.2f} (> cap US$ {BOOK_CAP}).")
            return "gate"
        if month_spend() + missing > MONTH_CAP and not (ap.get("month_cap_" + today()[:7]) or company_approvals().get("month_cap_" + today()[:7])):
            gate(name, "month_cap_" + today()[:7], f"Month spend would reach ~US$ {month_spend() + missing:.2f} (> cap {cap_txt()}).")
            return "gate"
        log(name, "pages", len(done), "/", len(L["pages"]))
        before = book_cost(folder)
        r = run([PY, f"{BIN}/page_line.py", folder], timeout=6 * 3600)
        open(f"{folder}/run.log", "a").write(r.stdout + r.stderr)
        spend(f"{name}: pages", book_cost(folder) - before)
        st = lj(f"{folder}/state.json", {})
    failed = [k for k, s in st.items() if s.get("state") == "human_queue"]
    if failed and not ap.get("failed_pages"):
        gate(name, "failed_pages", f"{len(failed)} pages failed 3 times ({', '.join(failed)}). "
             "Options: redo with a new theme, or continue without them (the number of designs on the cover changes).",
             [f"{folder}/attempts"])
        return "gate"

    # D. interior
    if not os.path.exists(f"{folder}/kit/interior.pdf") or os.path.getmtime(f"{folder}/kit/interior.pdf") < os.path.getmtime(f"{folder}/state.json"):
        log(name, "interior")
        L.setdefault("copyright", [c.format(year=datetime.date.today().year, brand=L["brand"]) for c in COPYRIGHT])
        sj(f"{folder}/book.json", L)
        r = run([PY, f"{BIN}/assemble.py", "interior", folder])
        if r.returncode:
            raise RuntimeError("interior: " + r.stderr[-400:])
    n_int = lj(f"{folder}/kit/interior.json")["interior_pages"]
    if n_int < 24 and not req.get("test"):
        raise RuntimeError(f"interior with {n_int} pages (KDP minimum 24)")

    # E. cover
    art = f"{folder}/kit/cover-art.png"
    if not os.path.exists(art):
        # Cleiton, 25 Nov 2026: the cream cover with a small vignette vanished in search. Now: art to the edge, strong colors,
        # people with faces, 3 candidates, and the storefront compares them as thumbnails with the competition before picking.
        if not L["cover"].get("mode"):
            L["cover"].update(mode="full_bleed", background_color=[253, 240, 219], outline_color=[110, 22, 22], accent_color=[220, 150, 40])
            sj(f"{folder}/book.json", L)
        moments = ["the main moment of the scene", "a closer, more intimate moment of the same idea, faces large",
                   "a wider moment of the same idea with more of the setting"]
        fronts = []
        for k, mom in zip("ABC", moments):
            fk = f"{folder}/kit/cover-art-{k}.png"
            if not os.path.exists(fk):
                log(name, f"cover art {k}")
                prompt = (L["cover"]["scene"] + f". Show {mom}. Full-bleed square illustration that fills the ENTIRE image "
                          "edge to edge, no empty margin, no border, no frame, no vignette. Bold and easy coloring-book line "
                          "art colored in: thick clean black outlines, big simple shapes, flat saturated colors, high contrast, "
                          "cheerful. Expressive people or animals with clear friendly faces, large, seen close up, all heads "
                          "and faces in the lower 60 percent of the image. The upper 40 percent is a calm, simple area (plain "
                          "wall or sky) where a title will be added later. No text, no letters, no numbers, no logos, no brand "
                          "or famous characters." + (" Art direction: " + L["cover_direction"] if L.get("cover_direction") else ""))
                r = run([PY, f"{BIN}/generate_image.py", "gpt-image-2", "low", fk, prompt], extra={"SIZE": "1024x1024"})
                if r.returncode:
                    raise RuntimeError("cover art: " + r.stdout[-300:])
                spend(f"{name}: cover art {k}", COVER_COST)
            r = run([PY, f"{BIN}/final_cover.py", f"{BOOKS}/fonts", fk, str(n_int), f"{folder}/kit/cover-cand-{k}"],
                    extra={"BOOK_JSON": f"{folder}/book.json"})
            if r.returncode:
                raise RuntimeError("cover candidate: " + r.stderr[-400:])
            from PIL import Image
            pv = Image.open(f"{folder}/kit/cover-cand-{k}-preview.png").convert("RGB")
            pv.crop((pv.width - int(8.625 * 300), 0, pv.width, pv.height)).save(f"{folder}/kit/front-{k}.jpg", quality=90)
            fronts.append((k, f"{folder}/kit/front-{k}.jpg"))
        log(name, "cover storefront")
        v = storefront(folder, L, fronts)
        good = [c for c in v["candidates"] if not c["title_covers_face"] and c["scene_matches_title"] and not c["problems"]]
        best = max(good, key=lambda c: c["storefront_score"]) if good else None
        if not best or best["storefront_score"] < 7:
            if not ap.get("cover_storefront"):
                gate(name, "cover_storefront", "No cover candidate passed the storefront (score 7+, no covered face). "
                     + v["rationale"], [f"{folder}/kit/storefront.png", f"{folder}/kit/storefront.json"])
                return "gate"
            best = max(v["candidates"], key=lambda c: c["storefront_score"])
        shutil.copy(f"{folder}/kit/cover-art-{best['id']}.png", art)
        log(name, "cover picked in the storefront", best["id"], best["storefront_score"])
    if not os.path.exists(f"{folder}/kit/cover.pdf") or os.path.getmtime(f"{folder}/kit/cover.pdf") < os.path.getmtime(f"{folder}/kit/interior.pdf"):
        log(name, "cover")
        approved = [st[p["id"]]["attempts"][-1]["file"] for p in L["pages"]
                    if st.get(p["id"], {}).get("state") == "approved"]
        r = run([PY, f"{BIN}/final_cover.py", f"{BOOKS}/fonts", art, str(n_int), f"{folder}/kit/cover"] + approved[:4],
                extra={"BOOK_JSON": f"{folder}/book.json"})
        if r.returncode:
            raise RuntimeError("cover: " + r.stderr[-400:])
        info = json.loads(r.stdout.strip().splitlines()[-1])
        if not info["title_inside_safe_zone"]:
            raise RuntimeError("cover title outside the safe zone")
        sj(f"{folder}/kit/cover.json", info)

    # F. listing
    if not os.path.exists(f"{folder}/kit/listing.json"):
        log(name, "listing")
        n_des = sum(1 for s in st.values() if s.get("state") == "approved")
        f = codex("Editor", (
            f"Prepare the KDP listing (paperback) for this book: title \"{L['title']}\", subtitle \"{L['subtitle']}\", "
            f"{n_des} designs, 8.5x8.5 in, single-sided pages, {n_int} pages, themes: "
            f"{'; '.join(p['theme'] for p in L['pages'][:12])}... Market: {req.get('market', 'Amazon.com')}.\n"
            "Give: title, subtitle, description (honest, no health promises, mentions single-sided pages), "
            "exactly 7 keywords (no third-party brands or authors, without repeating words from the title), 2 suggested "
            "categories, price_usd and price_eur (the code replaces the USD with pricing rule 0012), ai_disclosure (what to declare: interior and "
            "cover generated by AI, tool OpenAI gpt-image-2, with human editing), notes in English."),
            SCHEMA_LISTING, folder, f"{folder}/kit/listing.json")
        if len(f["keywords"]) != 7:
            raise RuntimeError(f"listing with {len(f['keywords'])} keywords")
        bench = lj(f"{folder}/benchmark.json")
        if bench:
            base = os.path.basename(folder)
            book_spend = sum(json.loads(l)["usd"] for l in open(SPEND) if base in json.loads(l)["desc"])
            cc = round(max(book_spend, book_cost(folder)), 2)
            pk = price_below("kdp", bench["prices"]["amazon"]["median"], n_int, cc)
            f.update(price_usd=pk["price"], kdp_price=pk)
            if "gumroad" in bench["prices"]:
                f["gumroad_price"] = price_below("gumroad", bench["prices"]["gumroad"]["median"], 0, cc)
            sj(f"{folder}/kit/listing.json", f)
    lst = lj(f"{folder}/kit/listing.json")
    if any(not lst.get(k, {"ok": True})["ok"] for k in ("kdp_price", "gumroad_price")) and not ap.get("price"):
        gate(name, "price", "No price below the competition leaves the book's creation cost on the 1st sale. "
             "See min_price_that_pays in kit/listing.json.",
             [f"{folder}/kit/listing.json", f"{folder}/BENCHMARK.md"])
        return "gate"

    # G. review of the whole book (Reviewer agent with all pages, cover and listing)
    rev_f = f"{folder}/kit/review.json"
    if not os.path.exists(rev_f) or os.path.getmtime(rev_f) < os.path.getmtime(f"{folder}/kit/cover.pdf"):
        log(name, "final review")
        errors, similar = checks(folder, L, st)
        lst = lj(f"{folder}/kit/listing.json")
        imgs = contact_sheets(folder, L, st) + [f"{folder}/kit/cover-preview.png"]
        themes = "\n".join(f"{p['id']}: {p['theme']}" for p in L["pages"])
        masc = L.get("mascot", "Toffee, a small chubby tabby cat" if "Toffee" in L.get("style", "") else None)
        masc_txt = f"Mascot: {masc}, should appear once on every page.\n" if masc else "No recurring mascot.\n"
        rv = codex("Revisor", (
            "You are the final quality reviewer of a complete adult coloring book before it goes to Amazon KDP. "
            "The attached contact sheets show every interior page, labelled with its id; the last image is the full cover "
            f"(back, spine, front). Title: {L['title']}. Subtitle: {L['subtitle']}. Brand: {L['brand']}. "
            + masc_txt + f"Page themes:\n{themes}\n"
            f"Listing description: {lst['description']}\nAutomatic checks found: {errors or 'nothing'}. "
            f"Near-identical page pairs by image hash: {similar or 'none'}.\n"
            f"FACTS (already verified by code, do not question them): the interior PDF has {n_int} pages; every drawing is "
            "printed on its own page with a blank back, so 'single-sided' is true; the cover title is inside the safe zone; "
            "every page already passed a per-page reviewer for text, gray shading, borders, cut-offs and deformities.\n"
            "Check the BOOK AS A WHOLE: readable text, letters or digits inside drawings; drawings cut off by the page edge; "
            + ("clearly deformed characters or objects; the mascot missing or twice on a page; " if masc else
               "clearly deformed animals, people or objects; ") + "pages that look like copies of each other; "
            "a page whose scene is clearly a different place than its theme; anything resembling a brand or copyrighted "
            "character; cover promises the interior does not keep; description claims that are false or promise health benefits.\n"
            "NOT defects (never list these): small extra details that fit the scene; a person in the scene; "
            + ("the mascot in a different pose or action than the theme says; small style differences of the mascot "
               "between pages; " if masc else "") + "hearts, dots, "
            "stripes, chocolate chips or blank shapes that are not readable letters; a full-color cover over black-and-white "
            "pages; anything you cannot see clearly at contact-sheet size.\n"
            "Only report what you can literally see. If you are not sure, it is not a defect. The pages are small on the "
            "sheets, so each page you list will be re-checked at full size by a second reviewer: list few, concrete defects "
            "with where they are in the drawing. Put in general_problems only real, verifiable problems with the cover or "
            "description, not doubts. Approve the book (approved=true) if no page needs redoing and there is no general problem. "
            "Score the whole book from 0 to 100 (100 = ready to sell). Write summary in English, 3-6 short sentences."),
            SCHEMA_REVIEW, folder, rev_f, imgs)
        # second look at full size: only confirmed defects remain
        theme_of = {p["id"]: p["theme"] for p in L["pages"]}
        confirmed, discarded = [], []
        for x in rv["pages_to_redo"]:
            if x["id"] not in theme_of:
                continue
            c = confirm(folder, x["id"], theme_of[x["id"]], x["reason"])
            (confirmed if c["confirmed"] else discarded).append(dict(x, evidence=c["evidence"]))
        rv.update(flagged=rv["pages_to_redo"], pages_to_redo=confirmed, discarded=discarded,
                  approved=not confirmed and not rv["general_problems"], checks=errors, similar=similar, date=today())
        sj(rev_f, rv)
        md = [f"# Final review: {L['title']}", "", f"{today()}. Score {rv['score']}/100. Approved: {'yes' if rv['approved'] else 'no'}.",
              "", rv["summary"], "", "## Pages to redo (confirmed at full size)"] + \
             [f"- {x['id']}: {x['reason']} ({x['evidence']})" for x in confirmed] + \
             ["", "## Flagged but discarded on the second look"] + [f"- {x['id']}: {x['reason']} ({x['evidence']})" for x in discarded] + \
             ["", "## General problems"] + [f"- {x}" for x in rv["general_problems"] + errors] + \
             ["", "## Similar pages (hash)"] + [f"- {x}" for x in similar]
        open(f"{folder}/kit/REVIEW.md", "w").write("\n".join(md) + "\n")
    rv = lj(rev_f)
    ids = {p["id"] for p in L["pages"]}
    redo = [x for x in rv["pages_to_redo"] if x["id"] in ids]
    if redo and L.get("review_rounds", 0) < 1:
        log(name, "reviewer orders redo", [x["id"] for x in redo])
        for x in redo:
            old = st.get(x["id"], {})
            st[x["id"]] = {"state": "pending", "attempts": [], "review_corrections": [x["reason"]],
                           "history": old.get("history", []) + old.get("attempts", [])}
        sj(f"{folder}/state.json", st)
        L["review_rounds"] = L.get("review_rounds", 0) + 1
        sj(f"{folder}/book.json", L)
        return book(t, name)
    if (not rv["approved"] or rv.get("checks")) and not ap.get("final_review"):
        gate(name, "final_review", f"The whole-book reviewer did not approve (score {rv['score']}/100). See the report.",
             [f"{folder}/kit/REVIEW.md"] + glob.glob(f"{folder}/kit/review/sheet-*.png"))
        return "gate"

    # H. archive: copies the finished book to ~/Finished-Books/<title>/
    dest = f"{ARCHIVE}/{slug(L['title'])}"
    sources = {"interior.pdf": f"{folder}/kit/interior.pdf", "cover.pdf": f"{folder}/kit/cover.pdf",
               "cover-preview.png": f"{folder}/kit/cover-preview.png", "listing.json": f"{folder}/kit/listing.json",
               "REVIEW.md": f"{folder}/kit/REVIEW.md"}
    if any(not os.path.exists(f"{dest}/{k}") or os.path.getmtime(f"{dest}/{k}") < os.path.getmtime(v) for k, v in sources.items()):
        log(name, "archive", dest)
        os.makedirs(dest, exist_ok=True)
        for k, v in sources.items():
            shutil.copy2(v, f"{dest}/{k}")
        L["archive"] = dest
        sj(f"{folder}/book.json", L)

    # I. kit
    lst = lj(f"{folder}/kit/listing.json")
    md = [f"# Upload kit: {lst['title']}", "", f"Generated {today()}. Upload only by Cleiton (decision 0009).", "",
          "## Files", "- Interior: kit/interior.pdf", "- Cover: kit/cover.pdf (see kit/cover-preview.png)", "",
          "## KDP form fields (in order)", f"- Title: {lst['title']}", f"- Subtitle: {lst['subtitle']}",
          f"- Author / brand: {L['brand']}", f"- Description:\n\n{lst['description']}\n",
          "- Keywords:\n" + "\n".join(f"  {i + 1}. {k}" for i, k in enumerate(lst["keywords"])),
          "- Categories: " + "; ".join(lst["categories"]), "- Low-content: do NOT tick", "- ISBN: free KDP ISBN",
          f"- AI-generated content: YES. {lst['ai_disclosure']}",
          "- Interior: black and white, white paper, 8.5 x 8.5 in, no bleed, glossy or matte cover (board)",
          f"- Price: US$ {lst['price_usd']} / EUR {lst['price_eur']} (EUR without benchmark: NOT VERIFIED)"] + \
         ([f"- Rule 0012 KDP: competitor median US$ {lst['kdp_price']['competitor_median']}, net US$ "
           f"{lst['kdp_price']['net_per_sale']}/sale, US$ {lst['kdp_price']['profit_after_irpf']} profit after IRPF"]
          if lst.get("kdp_price") else []) + \
         ([f"- Gumroad: US$ {lst['gumroad_price']['price']} (median US$ {lst['gumroad_price']['competitor_median']}, "
           f"net US$ {lst['gumroad_price']['net_per_sale']}/sale)"] if lst.get("gumroad_price") else []) + ["", "## Editor notes", lst["notes"], "",
          f"Estimated book cost: US$ {book_cost(folder):.2f}", "",
          f"Final review: score {rv['score']}/100 (kit/REVIEW.md). Copy saved in {dest}."]
    open(f"{folder}/kit/KIT.md", "w").write("\n".join(md))
    shutil.copy2(f"{folder}/kit/KIT.md", f"{dest}/KIT.md")

    # J. sprint review (decision 0012): does not block the upload
    if not os.path.exists(f"{folder}/kit/RETRO.md"):
        retro(name, folder, L, st, rv)
        shutil.copy2(f"{folder}/kit/RETRO.md", f"{dest}/RETRO.md")
    # K. personal Drive + spreadsheet: does not block the upload; retries on the next round if it fails
    try:
        drive_and_spreadsheet(name, folder, L, dest)
    except Exception as e:
        log(name, "drive", f"failed, will retry on the next round: {str(e)[:300]}")
    # L. Promoter (Cleiton's request, 23 Nov 2026): texts, images and DRAFTS for Gumroad, Etsy and Pinterest.
    #    Never publishes. Repeats at no cost (each step skips if the file already exists). Does not block the KDP upload.
    if not ap.get("promote"):
        try:
            r = run([PY, f"{BIN}/promote.py", folder], timeout=3600)
            if r.returncode:
                log(name, "promote", f"failed, will retry on the next round: {(r.stderr or r.stdout)[-300:]}")
        except Exception as e:
            log(name, "promote", f"failed, will retry on the next round: {str(e)[:300]}")
        if os.path.exists(f"{folder}/kit/PROMOTE.md"):
            gate(name, "promote", "Promotion ready as drafts (Gumroad, Etsy, 5 pins). Review kit/PROMOTE.md and publish. "
                 "Tell me when it is done.", [f"{folder}/kit/PROMOTE.md", f"{folder}/kit/channels.json",
                                              f"{folder}/kit/pinterest/pins.json"])
    if not ap.get("upload"):
        gate(name, "upload", f"Kit ready: review cover and interior and do the upload on KDP. Tell me when it is done.",
             [f"{dest}/KIT.md", f"{dest}/RETRO.md", f"{dest}/cover-preview.png", f"{dest}/interior.pdf"])
        return "gate"
    return "done"


# ----------------------------------------------------------------- research
SCHEMA_RESEARCH = {"type": "object", "additionalProperties": False,
                   "required": ["verdict", "confidence", "report_md"],
                   "properties": {"verdict": {"type": "string", "enum": ["enter", "test", "do_not_enter"]},
                                  "confidence": {"type": "integer"}, "report_md": {"type": "string"}}}

FIELDS = ["title", "author", "price", "listPrice", "stars", "reviewsCount", "bestsellerRanks", "monthlyPurchaseVolume",
          "productOverview", "aiReviewsSummary", "url", "input"]


def research(t, name):
    folder = f"{COMPANY}/projects/research/{t['id']}"
    os.makedirs(folder, exist_ok=True)
    ap = lj(f"{folder}/approvals.json", {})
    data = f"{folder}/data.json"
    if not os.path.exists(data):
        n = int(t.get("books_per_kw", 12))
        cost = len(t["keywords"]) * n * APIFY_COST_PER_BOOK
        if month_spend() + cost > MONTH_CAP and not (ap.get("month_cap_" + today()[:7]) or company_approvals().get("month_cap_" + today()[:7])):
            gate(name, "month_cap_" + today()[:7], f"Research would cost ~US$ {cost:.2f}; the month would go above the cap {cap_txt()}.")
            return "gate"
        short = apify_wait(cost)
        if short:
            info = serpapi_fallback(name, t["keywords"], n, short)
            if not info:
                log(name, "apify waiting", short)
                return "waiting"
        else:
            log(name, "apify", len(t["keywords"]), "keywords")
            r = run([PY, f"{BIN}/market_amazon2.py"] + t["keywords"], timeout=2400, extra={"BOOKS_PER_KW": str(n)})
            if r.returncode:
                raise RuntimeError("apify: " + (r.stdout + r.stderr)[-400:])
            info = json.loads(r.stdout.strip().splitlines()[-1])
            spend(f"{name}: apify", info.get("cost_usd") or cost)
        raw = lj(info["file"])
        lean = [{k: (it.get(k) if k != "aiReviewsSummary" else (it.get(k) or {}).get("text")) for k in FIELDS}
                for it in raw["items"]]
        sj(data, {"keywords": t["keywords"], "source": info["file"], "items": lean})
    if not os.path.exists(f"{folder}/analysis.json"):
        log(name, "analyst")
        a = codex("Analista", (
            f"Board question: {t['question']}\nData: the file data.json in this folder (Amazon.com books collected "
            "by Apify: price, stars, number of ratings, BSR, purchases/month, ratings summary). Read it.\n"
            "Assess the opportunity: demand (BSR, purchases/month), competition (how many with many ratings, age), "
            "prices (paperback vs hardcover), recurring complaints and praise, risks (health promises, puzzle spam, "
            "KDP rules), and what it would take for us to stand out. Separate measured facts from estimates. "
            "Never invent numbers. Write report_md in English, short, with a table of the 10 best books. "
            "Give verdict (enter/test/do_not_enter) and confidence 0-100."), SCHEMA_RESEARCH, folder, f"{folder}/analysis.json")
        open(f"{folder}/REPORT.md", "w").write(f"# Research: {t['id']}\n\nVerdict: {a['verdict']} "
                                               f"(confidence {a['confidence']}%)\n\n{a['report_md']}\n")
    a = lj(f"{folder}/analysis.json")
    if not ap.get("decided"):
        gate(name, "decide", f"Research ready: verdict {a['verdict']} ({a['confidence']}%). Decide whether we enter.",
             [f"{folder}/REPORT.md"])
        return "gate"
    return "done"


# ----------------------------------------------------------------- book of the day
SCHEMA_REQUEST = {"type": "object", "additionalProperties": False,
                  "required": ["slug", "niche", "keywords", "gumroad_query", "rationale"],
                  "properties": {"slug": {"type": "string"}, "niche": {"type": "string"}, "rationale": {"type": "string"},
                                 "gumroad_query": {"type": "string"},
                                 "keywords": {"type": "array", "items": {"type": "string"}}}}


def book_of_the_day():
    """Cleiton's rule (23 Nov 2026): 1 book per day up to the month's spend cap; at the cap it asks whether to go on."""
    reg_f = f"{COMPANY}/book-of-the-day.json"
    reg = lj(reg_f, {}) or {}
    if reg.get("last") == today():
        return
    key = "month_cap_" + today()[:7]
    if month_spend() >= MONTH_CAP and not company_approvals().get(key):
        gate("book-of-the-day", key, f"Month cap reached: spent US$ {month_spend():.2f} (cap {cap_txt()}). "
             "Do I go on with 1 book per day this month? (yes/no)")
        report_rows.append("| book-of-the-day | stopped at the month cap |")
        return
    tasks = [(f, lj(f, {})) for f in sorted(glob.glob(f"{QUEUE}/*.json"))]
    waiting = 0
    for f, t in tasks:
        if t.get("created_by") == "book_of_the_day" and t.get("state") != "done":
            if not (lj(f"{H(t['folder'])}/approvals.json", {}) or {}).get("brief"):
                waiting += 1
    if waiting >= MAX_BRIEFS_WAITING:
        report_rows.append(f"| book-of-the-day | not created: {waiting} briefs waiting for approval |")
        return
    existing = []
    for f, t in tasks:
        if t.get("type") == "book":
            L = lj(f"{H(t['folder'])}/book.json", {}) or {}
            existing.append(f"{L.get('title', '?')} | {(L.get('request') or {}).get('niche', '?')}")
    os.makedirs(f"{COMPANY}/book-of-the-day", exist_ok=True)
    log("book-of-the-day", "analyst")
    p = codex("Analista", (
        "Propose the next adult coloring book for MySandboxBooks (rule: 1 new book per day). "
        "Read the market data in market/ in this folder (junglee files and niches-*.log) and pick a niche with demand "
        "where we can do better. Do not repeat or nearly repeat these books we already have:\n- " + "\n- ".join(existing) +
        f"\nToday is {today()}: think of seasonal dates that still leave time (a book takes a few days to be ready). "
        + (("Cleiton's rule for December (until 23 Dec): alternate one Christmas book and one from another niche. The last book of the day was "
            f"'{reg.get('niche', 'none')}', so today is "
            + ("ANOTHER NICHE (not Christmas). " if "christmas" in (reg.get("niche") or "").lower() else
               "CHRISTMAS, with an angle different from the Christmas books we already have (another audience, another setting or another "
               "moment; the title must not look like one of our books). "))
           if today() <= "2026-12-23" else "") +
        "Rules: no third-party brands, characters, authors or art; no health promises; niche written in English "
        "as in the example 'cozy christmas coloring book for adults: warm holiday scenes at home...', with what must NOT appear. "
        "Give 3 real Amazon.com search keywords (the ones a buyer types), a short gumroad_query (2 words), "
        "a short lowercase slug with hyphens, and rationale in English with the facts from the data (separate measured from estimated, "
        "never invent numbers)."), SCHEMA_REQUEST, BOOKS, f"{COMPANY}/book-of-the-day/{today()}.json")
    sl = slug(p["slug"])[:40] or "book-" + today()
    folder = f"{BOOKS}/{sl}"
    while os.path.exists(folder):
        folder += "-2"
    os.makedirs(folder)
    template = lj(f"{BOOKS}/book-template.json", {}) or {}
    sj(f"{folder}/book.json", {
        "request": {"niche": p["niche"], "pages": 50, "language": "English",
                    "market": "Gumroad and Etsy (printable PDF) first; Amazon.com KDP later",
                    "keywords": p["keywords"][:3], "gumroad_query": p["gumroad_query"],
                    "analyst_rationale": p["rationale"], "created": today()},
        "brand": "MySandboxBooks", "style": template.get("style", "")})
    n = max([int(os.path.basename(f)[:3]) for f, _ in tasks if os.path.basename(f)[:3].isdigit()] + [0]) + 10
    sj(f"{QUEUE}/{n:03d}-{os.path.basename(folder)}.json",
       {"type": "book", "folder": "~/books/" + os.path.basename(folder), "created_by": "book_of_the_day", "created": today()})
    sj(reg_f, {"last": today(), "folder": folder, "niche": p["niche"]})
    log("book-of-the-day", "created", folder)


# ----------------------------------------------------------------- improvements and weekly review
def pending_improvements():
    """Each unticked improvement in improvements.md goes to the pending decisions. Cleiton approves ([x]) or rejects ([-])."""
    if not os.path.exists(IMPROVEMENTS):
        return
    todo = [l.strip()[6:] for l in open(IMPROVEMENTS) if l.strip().startswith("- [ ] ")]
    if todo:
        gate("improvements", "approve", f"{len(todo)} improvements from the retros to approve or reject:\n" +
             "\n".join(f"  {i}. {x}" for i, x in enumerate(todo, 1)), [IMPROVEMENTS])


SCHEMA_WEEK = {"type": "object", "additionalProperties": False,
               "required": ["summary", "numbers", "top3", "lessons"],
               "properties": {"summary": {"type": "string"},
                              "numbers": {"type": "array", "items": {"type": "string"}},
                              "lessons": {"type": "array", "items": {"type": "string"}},
                              "top3": {"type": "array", "items": {
                                  "type": "object", "additionalProperties": False,
                                  "required": ["type", "action", "expected_gain", "evidence"],
                                  "properties": {k: {"type": "string"} for k in ("type", "action", "expected_gain", "evidence")}}}}}


def weekly_review(force=False):
    """Friday (Cleiton's request, 23 Nov 2026): the Retro gathers the whole week and brings the 3 best improvements."""
    year, week, day = datetime.date.today().isocalendar()
    key = f"{year}-W{week:02d}"
    out = f"{COMPANY}/reports/week-{key}.md"
    if not force and (day != 5 or os.path.exists(out)):
        return
    since = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    books = []
    for m in glob.glob(f"{BOOKS}/*/kit/metrics.json"):
        if datetime.date.fromtimestamp(os.path.getmtime(m)).isoformat() >= since:
            books.append(lj(m, {}))
    spends = [json.loads(l) for l in open(SPEND) if l.strip() and json.loads(l)["date"] >= since]
    r = run([PY, f"{BIN}/sales.py"], timeout=600)
    sales = r.stdout.strip() if r.returncode == 0 else "no data (sales.py failed)"
    queue = []
    for f in sorted(glob.glob(f"{QUEUE}/*.json")):
        t = lj(f, {}) or {}
        queue.append(f"{os.path.basename(f)[:-5]}: {t.get('state', '?')}")
    to_approve = \
        [l.strip()[6:] for l in (open(IMPROVEMENTS) if os.path.exists(IMPROVEMENTS) else []) if l.strip().startswith("- [ ] ")]
    log("week", key, "retro")
    s = codex("Retro", (
        f"Weekly review {key} of the coloring book factory (from {since} to {today()}). Goal: spend as little "
        "as possible to deliver the best book and start selling.\n"
        f"Books finished this week (metrics measured by the code): {json.dumps(books, ensure_ascii=False) or 'none'}\n"
        f"Spend this week: {json.dumps(spends, ensure_ascii=False)}\n"
        f"Month spend: US$ {month_spend():.2f} of {cap_txt()}\n"
        f"Gumroad sales (Log Sales tab): {sales}\n"
        f"Queue: {'; '.join(queue)}\n"
        "Also read improvements.md and lessons.md in ~/company and the RETRO.md files in ~/books/*/kit/.\n"
        "Answer in English: summary (3-5 sentences), numbers (the most important ones, only the data here), new lessons "
        "Improvements already proposed and still awaiting approval (do NOT repeat them, rewrite them, or propose another one on the SAME problem):\n" +
        "\n".join(f"- {x}" for x in to_approve) + "\n"
        "(only those not yet in lessons.md) and top3: the 3 NEW improvements with the most gain for next week "
        "(if there are not 3 new ones with evidence, give fewer), each one "
        "with type (cost/time/quality/sales), concrete action, expected gain and the evidence. Use only the numbers given; "
        "never invent. Code changes are proposals: the board approves."),
        SCHEMA_WEEK, COMPANY, f"{COMPANY}/reports/week-{key}.json")
    md = [f"# Weekly review {key}", "", f"{since} to {today()}. Done by the Retro.", "", s["summary"], "", "## Numbers"]
    md += [f"- {x}" for x in s["numbers"]] + ["", "## Top 3 improvements (board approves)"]
    md += [f"{i}. [{x['type']}] {x['action']} (gain: {x['expected_gain']}; why: {x['evidence']})"
           for i, x in enumerate(s["top3"], 1)]
    md += ["", "## New lessons"] + [f"- {x}" for x in s["lessons"]]
    open(out, "w").write("\n".join(md) + "\n")
    with open(IMPROVEMENTS, "a") as f:
        f.write(f"\n## {today()} Weekly review {key} (proposals, board approves)\n" +
                "".join(f"- [ ] [{x['type']}] {x['action']} (gain: {x['expected_gain']})\n" for x in s["top3"]))
    if s["lessons"]:
        with open(LESSONS, "a") as f:
            f.write(f"\n## Week {key}\n" + "".join(f"- {x}\n" for x in s["lessons"]))
    gate("weekly-review", key, f"Weekly review ready: {s['summary'][:300]}", [out])


# ----------------------------------------------------------------- cycle
def report():
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    p = ["# Pending decisions (human)", "", f"Updated {time.strftime('%Y-%m-%d %H:%M')} by the factory.", ""]
    for d in pending or [{"task": "-", "decision": "-", "text": "Nothing pending.", "files": []}]:
        p.append(f"- **{d['task']}** [{d['decision']}]: {d['text']}")
        for f in d["files"]:
            p.append(f"  - {f}")
    open(PENDING, "w").write("\n".join(p) + "\n")
    r = ["# Factory: status", "", f"Updated {time.strftime('%Y-%m-%d %H:%M')}. Month spend: US$ {month_spend():.2f} "
         f"(cap {cap_txt()}).", "", "| Task | Status |", "|---|---|"] + report_rows
    open(REPORT, "w").write("\n".join(r) + "\n")


def commit():
    run(["git", "add", "-A", "decisions/pending.md", "reports/factory.md", "queue", "projects", "spend.jsonl", "improvements.md", "lessons.md", "config.json", "decisions", "book-of-the-day", "book-of-the-day.json", "exchange_rate.json", "approvals.json", "watchdog.json"], cwd=COMPANY)
    if run(["git", "diff", "--cached", "--quiet"], cwd=COMPANY).returncode:
        run(["git", "commit", "-qm", "Factory: status " + time.strftime("%Y-%m-%d %H:%M")], cwd=COMPANY)
        run(["git", "push", "-q"], cwd=COMPANY, timeout=120)


def main():
    os.makedirs(QUEUE, exist_ok=True)
    open(SPEND, "a").close()
    lock = f"{BOOKS}/.factory.lock"
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 8 * 3600:
        log("another run in progress; exiting"); return
    open(lock, "w").write(str(os.getpid()))
    global MONTH_CAP
    MONTH_CAP = USD_CAP_BY_MONTH.get(today()[:7]) or round(MONTH_CAP_EUR * usd_per_eur(), 2)
    try:
        if "--status" not in sys.argv and "--no-book-of-the-day" not in sys.argv:
            try:
                book_of_the_day()
            except Exception as e:
                gate("book-of-the-day", "error", f"Could not create the book of the day: {str(e)[:300]}")
        for f in sorted(glob.glob(f"{QUEUE}/*.json")):
            t = lj(f)
            name = os.path.basename(f)[:-5]
            if t.get("state") == "done":
                report_rows.append(f"| {name} | done |"); continue
            try:
                if "--status" in sys.argv:
                    res = t.get("state", "?")
                else:
                    res = (book if t["type"] == "book" else research)(t, name)
                    t["state"], t["error"] = res, None
            except Exception as e:  # an error in one task does not stop the others
                t["state"], t["error"] = "error", str(e)[:500]
                gate(name, "error", f"The factory stopped on this task: {t['error']}")
                res = "error"
            t["updated"] = time.strftime("%Y-%m-%d %H:%M")
            sj(f, t)
            report_rows.append(f"| {name} | {res} |")
            log(name, "->", res)
        # Sales log (Cleiton's request): Log Sales tab, every 6 hours. Failing here does not stop the factory.
        mv = f"{COMPANY}/.sales.mark"
        if "--status" not in sys.argv and (not os.path.exists(mv) or time.time() - os.path.getmtime(mv) > 6 * 3600):
            try:
                r = run([PY, f"{BIN}/sales.py"], timeout=600)
                if r.returncode == 0:
                    open(mv, "w").write(r.stdout.strip())
                    report_rows.append(f"| sales-log | {r.stdout.strip()} |")
                else:
                    log("sales", "failed", (r.stderr or r.stdout)[-300:])
            except Exception as e:
                log("sales", "failed", str(e)[:300])
        if "--status" not in sys.argv:
            try:
                weekly_review("--week" in sys.argv)
            except Exception as e:
                gate("weekly-review", "error", f"The weekly review failed: {str(e)[:300]}")
        pending_improvements()
        report()
        commit()
    finally:
        os.remove(lock)


if __name__ == "__main__":
    main()
