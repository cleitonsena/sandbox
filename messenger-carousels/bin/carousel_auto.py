#!/usr/bin/env python3
"""carousel_auto (26 Nov 2026, decision 0026): the Your Bestie, The Messenger profile runs on its own.
Every day: 3 new carousels (script by a free LLM, reviewer, low-quality GPT art + title drawn in code),
published at 15:30, 18:30 and 21:30 (machine local time, TIMEZONE below):
  Instagram  -> Zernio (second free account), scheduled, AI label isAiGenerated
  TikTok     -> Zernio (free plan), scheduled, automatic music, AI notice in the caption
  X          -> official API, pay per use (~USD 0.015 per post), made_with_ai + AI notice in the text
Without the key for a network, that network stays in "dry-run" (nothing goes out) and the rest carries on.

Usage:
  carousel_auto.py cycle             # what launchd runs every 15 min: builds the day, schedules, publishes what is due
  carousel_auto.py generate [--date YYYY-MM-DD] [--force]
  carousel_auto.py status [--date YYYY-MM-DD]
Files: ~/prototypes/posters/auto/YYYY-MM-DD/ (scripts, images, queue.json); log in ~/company/log.md and
~/company/projects/posters/carousel-history.jsonl. Keys in chmod 600 files, never printed."""
import datetime as dt, json, os, re, subprocess, sys, time, traceback
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
H = os.path.expanduser
COMPANY = H("~/company"); BASE = H("~/prototypes/posters/auto")
HISTORY = f"{COMPANY}/projects/posters/carousel-history.jsonl"; SPEND = f"{COMPANY}/spend.jsonl"
GEMINI = [H("~/.venv-genai/bin/python"), H("~/books/bin/gemini_json.py")]
BIN_IMG = H("~/books/bin/generate_image.py")
HOURS = ["15:30", "18:30", "21:30"]
IMG_COST = 0.0067           # gpt-image-2 low 1024x1536 (earlier batch: 9 images ~USD 0.06)
X_COST = 0.015              # per post without a link (docs.x.com pricing)
CAP = {"2026-12": 30.0}     # decision 0023; other months: the default below (conservative, in USD)
DEFAULT_CAP = 10.5
AI_NOTICE = "Art made with AI."


def format_x(t):
    """X: one paragraph per sentence, with a blank line (like the hand-made posts). Keeps breaks already there."""
    t = t.strip()
    if "\n\n" in t: return t
    return "\n\n".join(s.strip() for s in re.split(r"(?<=[.?!])\s+", t) if s.strip())
FOLLOW = "Follow for more messages like this."


def today(): return dt.date.today().isoformat()
def now(): return dt.datetime.now()
def rj(p, d=None):
    try: return json.load(open(p))
    except Exception: return d
def wj(p, d):
    t = p + ".tmp"; json.dump(d, open(t, "w"), ensure_ascii=False, indent=1); os.replace(t, p)
def secret(name):
    p = H(f"~/.{name}")
    return open(p).read().strip() if os.path.exists(p) else None


def log(*a):
    line = f"- {now():%Y-%m-%d %H:%M} carousels: " + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(f"{COMPANY}/log.md", "a") as f: f.write(line + "\n")


def spend(desc, usd):
    with open(SPEND, "a") as f:
        f.write(json.dumps({"date": today(), "desc": desc, "usd": round(usd, 4)}, ensure_ascii=False) + "\n")


def month_spend():
    m, tot = today()[:7], 0.0
    if os.path.exists(SPEND):
        for l in open(SPEND):
            try:
                r = json.loads(l)
                if r["date"].startswith(m): tot += r["usd"]
            except Exception: pass
    return tot


def fits(usd):
    """same gate as the book factory: above the cap only with month_cap_YYYY-MM approved in ~/company/approvals.json"""
    cap = CAP.get(today()[:7], DEFAULT_CAP)
    approved = (rj(f"{COMPANY}/approvals.json", {}) or {}).get("month_cap_" + today()[:7])
    return bool(approved) or month_spend() + usd <= cap, cap


# ----------------------------------------------------------------- script
SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["posts"],
          "properties": {"posts": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
              "type": "object", "additionalProperties": False,
              "required": ["key", "theme", "word", "tt_title", "slides", "caption", "x_text"],
              "properties": {
                  "key": {"type": "string"}, "theme": {"type": "string"}, "word": {"type": "string"},
                  "tt_title": {"type": "string"}, "caption": {"type": "string"}, "x_text": {"type": "string"},
                  "slides": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
                      "type": "object", "additionalProperties": False, "required": ["pos", "scene", "lines"],
                      "properties": {"pos": {"type": "string", "enum": ["top", "bottom"]}, "scene": {"type": "string"},
                                     "lines": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
                                         "type": "object", "additionalProperties": False, "required": ["t", "k"],
                                         "properties": {"t": {"type": "string"}, "k": {"type": "number"}}}}}}}}}}}}

REVIEW_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["results"],
                 "properties": {"results": {"type": "array", "items": {
                     "type": "object", "additionalProperties": False, "required": ["key", "approved", "problems"],
                     "properties": {"key": {"type": "string"}, "approved": {"type": "boolean"},
                                    "problems": {"type": "array", "items": {"type": "string"}}}}}}}

REQUEST = """You write 3 Instagram/TikTok carousels for "Your Bestie, The Messenger" (@yourbestiethemessenger):
affirmations, manifestation and light spiritual wisdom, in ENGLISH, warm and direct, like a wise best friend.

Read these files first (ours; rules, references and past posts):
- ~/company/decisions/0025-your-bestie-profile.md
- ~/company/decisions/0026-your-bestie-auto-publishing.md
- ~/company/projects/posters/references.md
- ~/company/projects/posters/reviews.md
- ~/company/projects/posters/caption-example.md   (style example of a finished caption)
- ~/company/projects/posters/carousel-history.jsonl (themes already used: NEVER repeat a theme or hook)

Each carousel = 3 message slides (a 4th CTA slide is added by code). Rules:
- Slide 1: a hook with tension, or a NAMED concept (e.g. "the 3-second rule of self-talk"), max 4 short lines.
- Slide 2: the turn. Slide 3: a line to complete or an open question (Investment).
- Each slide: 2-3 lines, each line max 22 characters, lowercase except "I" and proper words; one line per slide
  has k between 1.3 and 1.5 (the big line), the others k=1.
- pos alternates: slide 1 "top", slide 2 "bottom", slide 3 "top" (or the reverse). The empty paper zone is where
  the title goes.
- scene: one English sentence describing ONE simple scene, starting with "In the lower two thirds," when pos is
  "top" and "In the upper two thirds," when pos is "bottom". One person (silhouette) or one symbolic object;
  vary composition (frame inside frame, tiny figure + huge sky, close profile). No text, no clocks with digits.
- word: ONE word or very short phrase (max 14 chars) people comment, related to the post.
- tt_title: TikTok title, max 80 chars, the hook as a sentence. It must say what the slides say: never name
  a rule, number or concept that is not on the slides.
- caption: 900-1600 chars. Hook line first. Short lines. A personal "I've been there too" part, the turn,
  a question, then CTA lines: comment the word, save it, send it to someone specific. Then a blank line and
  exactly "{follow}" as the last line. Max 1 emoji (🤍) in the whole caption. No hashtags. No @mentions. No links.
- x_text: max 220 chars, 4 short paragraphs separated by ONE blank line (\n\n): the hook as a question, one
  insight, a reflective question, then exactly: Reply "<word>" if <short reason>. No hashtags, no links.
- key: short lowercase slug of the theme (a-z, 0-9, -), unique.

Hard limits (an automatic reviewer rejects otherwise): no promise of results ("you will attract", "guaranteed"),
no health, healing, cure, therapy, anxiety or depression claims, no money promises, no science words like Hz,
frequency, quantum, vibration numbers, dopamine; no real brands, books, people, quotes or religions by name;
never copy phrases from the reference profiles; nothing about the reader's body or appearance.
Make the 3 carousels different in theme (e.g. one on self-talk/identity, one on letting go/choices, one on
signs/intuition/manifestation) and different from everything in carousel-history.jsonl."""

REVIEW_REQUEST = """You are the strict reviewer of an automated affirmation profile that publishes WITHOUT a human.
Read ~/company/decisions/0026-your-bestie-auto-publishing.md and the carousels in {file}.
Reject a carousel (approved=false) if ANY slide line, caption, title or X text:
- promises a result or outcome (money, love, success, "will manifest", "guaranteed", "the universe will give");
- makes a health, healing, cure, therapy or mental-illness claim, or gives medical advice;
- uses pseudo-science (Hz, frequency, quantum, vibration numbers, brain chemicals) as fact;
- names a real brand, product, book, living or historical person, religion or deity, or quotes someone;
- shames the reader, targets body or appearance, or could hurt someone in crisis;
- has spelling/grammar errors, hashtags, links, @mentions, or more than one emoji;
- is incoherent between slides, caption and X text;
- has a tt_title that names a concept, rule or number (e.g. "the 3-second rule") which the slides do not
  actually show, or a caption/X text about a different idea than the slides.
List each problem in plain English. Approve only if you would sign it."""

FORBIDDEN = re.compile(r"(?i)\b(cure[sd]?|curing|heal(?:s|ed|ing)?|therap\w*|anxiety|depress\w*|diagnos\w*|guarantee\w*|"
                       r"hz|hertz|frequenc\w*|quantum|dopamine|serotonin|cortisol|doctor|medic\w*|disease|illness|"
                       r"will attract|will manifest|millionaire|get rich|lose weight|weight loss|#\w+|https?://|www\.|@\w+)")


def rules(p):
    """deterministic reviewer; returns a list of problems"""
    pr = []
    texts = [l["t"] for s in p["slides"] for l in s["lines"]] + [p["caption"], p["x_text"], p["tt_title"], p["word"]]
    for t in texts:
        for m in FORBIDDEN.finditer(t): pr.append(f"forbidden word: {m.group(0)!r}")
    if len(format_x(p["x_text"])) + 2 + len(AI_NOTICE) > 280: pr.append("x_text too long")
    if len(p["tt_title"]) > 90: pr.append("tt_title > 90")
    if len(p["word"]) > 16: pr.append("word too long")
    if not p["caption"].rstrip().endswith(FOLLOW): pr.append("caption does not end with the follow line")
    if len(p["caption"]) > 2000: pr.append("caption > 2000")
    if sum(p["caption"].count(e) for e in "🤍❤️✨🙏💫🌙") > 1: pr.append("more than 1 emoji")
    for s in p["slides"]:
        if any(len(l["t"]) > 26 for l in s["lines"]): pr.append("slide line > 26 characters")
    if not re.fullmatch(r"[a-z0-9-]{2,40}", p["key"]): pr.append("invalid key")
    return sorted(set(pr))


def llm(request, schema, output, folder):
    fr, fs = f"{folder}/.request.txt", f"{folder}/.schema.json"
    open(fr, "w").write(request); wj(fs, schema)
    r = subprocess.run(GEMINI + ["--request", fr, "--schema", fs, "--output", output, "--cwd", COMPANY],
                       capture_output=True, text=True, timeout=900)
    if r.returncode or not os.path.exists(output):
        raise RuntimeError("LLM failed: " + (r.stderr or r.stdout)[-300:])
    return rj(output)


def script(folder):
    """up to 3 rounds: write, review (rules + LLM), redo only what was rejected"""
    good, rejected = [], []
    for rnd in range(3):
        missing = 3 - len(good)
        if missing == 0: break
        extra = ""
        if good: extra += "\nAlready approved today (do not repeat these themes): " + ", ".join(p["theme"] for p in good)
        if rejected: extra += "\nRejected earlier, avoid these problems: " + json.dumps(rejected[-6:], ensure_ascii=False)
        d = llm(REQUEST.replace("{follow}", FOLLOW) + extra, SCHEMA, f"{folder}/script-v{rnd}.json", folder)
        cand = d["posts"][:missing] if missing < 3 else d["posts"]
        wj(f"{folder}/candidates.json", cand)
        rev = llm(REVIEW_REQUEST.replace("{file}", f"{folder}/candidates.json"), REVIEW_SCHEMA,
                  f"{folder}/review-v{rnd}.json", folder)
        verdict = {r["key"]: r for r in rev["results"]}
        for p in cand:
            pr = rules(p) + ([] if verdict.get(p["key"], {}).get("approved") else
                             verdict.get(p["key"], {}).get("problems", ["reviewer did not assess it"]))
            if pr or any(p["key"] == b["key"] for b in good):
                rejected.append({"theme": p["theme"], "problems": pr or ["repeated key"]})
                log("rejected", p["key"], "|", "; ".join(pr)[:300])
            else:
                good.append(p)
    wj(f"{folder}/rejected.json", rejected)
    return good


# ----------------------------------------------------------------- art
def art(folder, posts):
    import numpy as np
    from PIL import Image
    import carousel_art as A
    tasks = [(p, i) for p in posts for i in range(3)]
    new = [t for t in tasks if not os.path.exists(f"{folder}/{t[0]['key']}-bg-{t[1] + 1}.png")]
    ok, cap = fits(len(new) * IMG_COST)
    if not ok:
        raise RuntimeError(f"the monthly cap (USD {cap:.2f}) does not allow generating {len(new)} images")

    def one(t):
        p, i = t; s = p["slides"][i]; f = f"{folder}/{p['key']}-bg-{i + 1}.png"
        prompt = A.STYLE.format(scene=s["scene"], empty="top" if s["pos"] == "top" else "bottom")
        r = subprocess.run([sys.executable, BIN_IMG, "gpt-image-2", "low", f, prompt], capture_output=True, text=True,
                           env=dict(os.environ, SIZE="1024x1536"), timeout=600)
        if r.returncode: return f, r.stdout[-200:] + r.stderr[-200:]
        spend(f"carousel {p['key']} bg {i + 1}", IMG_COST); return f, "ok"
    with ThreadPoolExecutor(3) as ex:
        for f, res in ex.map(one, new):
            if res != "ok": raise RuntimeError(f"image failed {os.path.basename(f)}: {res}")
    for p in posts:
        for i, s in enumerate(p["slides"]):
            A.slide(f"{folder}/{p['key']}-bg-{i + 1}.png", f"{folder}/{p['key']}-{i + 1}.png",
                    i + 1, 4, [(l["t"], float(l["k"])) for l in s["lines"]], s["pos"])
        A.slide_cta(f"{folder}/{p['key']}-4.png", p["word"])
        for n in range(1, 5):  # JPEG 1080x1350 for the networks (Instagram only accepts JPEG)
            Image.open(f"{folder}/{p['key']}-{n}.png").convert("RGB").save(f"{folder}/{p['key']}-{n}.jpg", quality=92)
    A.contact_sheet(folder, [p["key"] for p in posts])


# ----------------------------------------------------------------- day
def generate(date, force=False):
    folder = f"{BASE}/{date}"; os.makedirs(folder, exist_ok=True); queue_p = f"{folder}/queue.json"
    if os.path.exists(queue_p) and not force: return rj(queue_p)
    posts = script(folder)
    if not posts:
        log("day", date, "no carousel approved by the reviewer; nothing goes out today"); wj(queue_p, {"date": date, "posts": []})
        return rj(queue_p)
    art(folder, posts)
    queue = {"date": date, "created": now().isoformat(timespec="seconds"), "posts": []}
    for p, hour in zip(posts, HOURS):
        cap = p["caption"].rstrip()
        cap = cap[: -len(FOLLOW)].rstrip() + "\n\n" + FOLLOW
        queue["posts"].append({
            "key": p["key"], "theme": p["theme"], "hour": hour,
            "images": [f"{folder}/{p['key']}-{n}.jpg" for n in range(1, 5)],
            "caption_ig": cap + "\n\n" + AI_NOTICE,
            "caption_tt": cap + "\n\n" + AI_NOTICE, "tt_title": p["tt_title"][:90],
            "x_text": format_x(p["x_text"]) + "\n\n" + AI_NOTICE,
            "networks": {"instagram": {"state": "pending"}, "tiktok": {"state": "pending"}, "x": {"state": "pending"}}})
        with open(HISTORY, "a") as f:
            f.write(json.dumps({"date": date, "key": p["key"], "theme": p["theme"], "hook": p["slides"][0]["lines"][0]["t"],
                                "word": p["word"]}, ensure_ascii=False) + "\n")
    wj(queue_p, queue)
    log("day", date, "ready:", ", ".join(f"{x['hour']} {x['key']}" for x in queue["posts"]))
    return queue


def cycle():
    import connectors as C
    date = today(); folder = f"{BASE}/{date}"; queue_p = f"{folder}/queue.json"
    if now().hour < 8: return
    if os.path.exists(f"{folder}/.failed") and time.time() - os.path.getmtime(f"{folder}/.failed") < 3600: return
    try:
        queue = generate(date)
    except Exception as e:
        os.makedirs(folder, exist_ok=True); open(f"{folder}/.failed", "w").write(traceback.format_exc())
        log("ERROR generating", date, str(e)[:300]); return
    changed = False
    for p in queue["posts"]:
        when = dt.datetime.fromisoformat(f"{date}T{p['hour']}:00")
        for net, fn, ahead in (("tiktok", C.tiktok, True), ("instagram", C.instagram, True), ("x", C.x, False)):
            e = p["networks"][net]
            if e["state"] in ("done", "scheduled", "final-error"): continue  # "dry-run" retries: the key may have arrived
            if not ahead and now() < when: continue
            if now() > when + dt.timedelta(hours=2) and not ahead:
                e.update(state="final-error", note="missed the 2 h window"); changed = True; continue
            try:
                res = fn(p, when); prev_state = e["state"]
                e.update(res); changed = True
                if e["state"] == "dry-run" and prev_state == "dry-run": continue
                log(net, p["key"], e["state"], e.get("id", ""), e.get("note", ""))
                if net == "x" and e["state"] == "done": spend(f"carousel X {p['key']}", X_COST)
            except Exception as ex:
                e["attempts"] = e.get("attempts", 0) + 1; e["note"] = str(ex)[:300]; changed = True
                if e["attempts"] >= 4: e["state"] = "final-error"
                log("ERROR", net, p["key"], f"attempt {e['attempts']}:", str(ex)[:300])
    if changed: wj(queue_p, queue)


def status(date):
    q = rj(f"{BASE}/{date}/queue.json")
    if not q: print("no queue for", date); return
    for p in q["posts"]:
        print(p["hour"], p["key"], " ".join(f"{n}={v['state']}" for n, v in p["networks"].items()))


if __name__ == "__main__":
    a = sys.argv[1:] or ["cycle"]
    d = a[a.index("--date") + 1] if "--date" in a else today()
    if a[0] == "cycle": cycle()
    elif a[0] == "generate": generate(d, "--force" in a); status(d)
    elif a[0] == "status": status(d)
    else: print(__doc__)
