#!/usr/bin/env python3
"""Assembly line for one coloring book (pilot, board decision 2026-11-21).

Usage: page_line.py BOOK_FOLDER
The folder has book.json: {"style": "...{theme}...", "size": "1024x1024",
"pages": [{"id": "p01", "theme": "..."}]}
For each page: generate -> automatic check -> reviewer (codex, subscription) ->
approved? vectorise/upscale : redo the SAME page (max 3) -> human queue.
State in state.json: if it stops, it resumes where it left off. Publishes nothing, never opens Amazon.
"""
import json, os, subprocess, sys, time
from PIL import Image

BIN = os.path.expanduser("~/books/bin")
MAX_ATTEMPTS = 3
IMG_COST = 0.02  # measured 2026-11-21: US$ 0.06 for 3 images
PRINT_SIDE = 2550  # 8.5 in x 300 dpi

folder = os.path.abspath(sys.argv[1]) if not sys.argv[1].startswith("--") else os.getcwd()
f_state = os.path.join(folder, "state.json")
state = json.load(open(f_state)) if os.path.exists(f_state) else {}
if not sys.argv[1].startswith("--"):
    os.makedirs(os.path.join(folder, "attempts"), exist_ok=True)
    os.makedirs(os.path.join(folder, "final"), exist_ok=True)


def save():
    with open(f_state, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def check(path):
    """Rules measured on the pixels. Returns a list of problems (empty = ok)."""
    im = Image.open(path).convert("L")
    w, h = im.size
    px = im.load()
    total = w * h
    hist = im.histogram()
    gray = sum(hist[40:216]) / total
    black = sum(hist[:40]) / total
    probs = []
    if gray > 0.06:
        probs.append(f"too much gray or shading ({gray:.0%} gray pixels); use pure black lines on pure white")
    if black > 0.30:
        probs.append(f"too much solid black ({black:.0%}); keep large white areas to color")
    if black < 0.02:
        probs.append("lines too thin or too few; use thick bold outlines")
    # page frame = long dark line near the edge on at least 3 sides
    # (1 or 2 sides = content, e.g. a shelf or a window; calibrated on pilot 01)
    sides = 0
    for name in ("top", "bottom", "left", "right"):
        for frac in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06):
            if name == "top": line = [px[x, int(h * frac)] for x in range(w)]
            elif name == "bottom": line = [px[x, int(h * (1 - frac))] for x in range(w)]
            elif name == "left": line = [px[int(w * frac), y] for y in range(h)]
            else: line = [px[int(w * (1 - frac)), y] for y in range(h)]
            if sum(1 for v in line if v < 100) / len(line) > 0.6:
                sides += 1
                break
    if sides >= 3:
        probs.append("there is a rectangular border or frame around the page; remove it")
    # margin: on each side, the outer 1.5% band must be almost all white
    b = max(2, int(w * 0.015))
    bands = {
        "top": [px[x, y] for x in range(w) for y in range(b)],
        "bottom": [px[x, y] for x in range(w) for y in range(h - b, h)],
        "left": [px[x, y] for y in range(h) for x in range(b)],
        "right": [px[x, y] for y in range(h) for x in range(w - b, w)],
    }
    cut = [n for n, v in bands.items() if sum(1 for p_ in v if p_ < 100) / len(v) > 0.06]
    if cut:
        probs.append("objects are cut off by the page edge (" + ", ".join(cut) + "); keep the whole drawing inside with a white margin")
    return probs


SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["defects", "suggestions", "score"],
          "properties": {"defects": {"type": "array", "items": {"type": "string"}},
                         "suggestions": {"type": "array", "items": {"type": "string"}},
                         "score": {"type": "integer"}}}


def reviewer(path, theme):
    f_schema = os.path.join(folder, "reviewer-schema.json")
    json.dump(SCHEMA, open(f_schema, "w"))
    f_out = path + ".review.json"
    request = (
        "You are the quality reviewer of an adult coloring book (cozy, bold and easy style). "
        f"Look at the attached page. Intended theme: {theme}. "
        "A DEFECT is only one of these: 1) theme not recognisable; 2) gray shading or filled areas instead of outlines; "
        "3) any text, letters, numbers or watermark; 4) deformed hands, faces, animals or objects; "
        "5) many areas too tiny to color with a fine marker; 6) a border or frame around the page; "
        "7) main objects cut off by the page edge; 8) anything resembling a known brand, logo or copyrighted character. "
        "Everything else (could be simpler, could be nicer) is a SUGGESTION, not a defect. "
        "Be fair: a clean, usable page with no defects must pass even if it could be improved. "
        "Score 1-10. Write each defect and suggestion as a short instruction in English for the illustrator. "
        "Do not run any commands; just look at the image and answer."
    )
    cmd = ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "-i", path,
           "--output-schema", f_schema, "-o", f_out, request]
    env = dict(os.environ, PATH="/opt/homebrew/bin:" + os.path.expanduser("~/.local/bin") + ":" + os.environ["PATH"])
    t0 = time.time()
    r = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, timeout=600, env=env, stdin=subprocess.DEVNULL)
    try:
        out = json.load(open(f_out))
    except Exception:
        return {"approved": False, "score": 0, "defects": [], "problems": ["reviewer failed: " + r.stderr[-300:]],
                "seconds": round(time.time() - t0, 1), "reviewer_error": True}
    out["seconds"] = round(time.time() - t0, 1)
    out["approved"] = not out.get("defects")
    out["problems"] = out.get("defects", [])
    return out


SAFE_MARGIN = 113  # 0.375 in at 300 dpi (KDP inside margin 24-150 pages, verified 2026-11-21)


def upscale(src, dst):
    """Upscales to 2550x2550 at 300 dpi, 1 bit, with a white safety margin."""
    side = PRINT_SIDE - 2 * SAFE_MARGIN
    im = Image.open(src).convert("L").resize((side, side), Image.LANCZOS)
    canvas = Image.new("L", (PRINT_SIDE, PRINT_SIDE), 255)
    canvas.paste(im, (SAFE_MARGIN, SAFE_MARGIN))
    canvas.point(lambda v: 255 if v > 150 else 0).convert("1").save(dst, dpi=(300, 300))


if sys.argv[1] == "--check":  # tests the rules on images already made, without generating anything
    import glob
    for f in sorted(glob.glob(os.path.join(sys.argv[2], "*.png"))):
        print(os.path.basename(f), check(f) or "OK")
    sys.exit(0)
if sys.argv[1] == "--review":  # tests only the reviewer: --review FOLDER IMG "theme"
    folder = os.path.abspath(sys.argv[2])
    print(json.dumps(reviewer(os.path.abspath(sys.argv[3]), sys.argv[4]), ensure_ascii=False))
    sys.exit(0)
book = json.load(open(os.path.join(folder, "book.json")))

for pg in book["pages"]:
    st = state.setdefault(pg["id"], {"state": "pending", "attempts": []})
    if st["state"] in ("approved", "human_queue"):
        continue
    corrections = list(st.get("review_corrections", []))  # coming from the whole-book review
    for t in st["attempts"]:
        corrections += t.get("problems", [])
    while len(st["attempts"]) < MAX_ATTEMPTS:
        n = len(st["attempts"]) + 1
        prompt = book["style"].format(theme=pg["theme"])
        if corrections:
            prompt += " Important corrections: " + "; ".join(dict.fromkeys(corrections)) + "."
        img = os.path.join(folder, "attempts", f"{pg['id']}-t{n}.png")
        g = subprocess.run([sys.executable, os.path.join(BIN, "generate_image.py"), "gpt-image-2", "low", img, prompt],
                           capture_output=True, text=True, env=dict(os.environ, SIZE=book.get("size", "1024x1024")))
        rec = {"n": n, "file": img, "est_cost": IMG_COST}
        if g.returncode != 0:
            rec.update(stage="generate", problems=[], error=g.stdout[-300:])
            st["attempts"].append(rec); save()
            print(pg["id"], "t", n, "ERROR generate", g.stdout[-200:], flush=True)
            continue
        rec["generate"] = json.loads(g.stdout.strip().splitlines()[-1])
        probs = check(img)
        if probs:
            rec.update(stage="check", problems=probs)
        else:
            rv = reviewer(img, pg["theme"])
            rec.update(stage="reviewer", reviewer=rv, problems=rv.get("problems", []))
            if rv.get("approved"):
                upscale(img, os.path.join(folder, "final", pg["id"] + ".png"))
                st["state"] = "approved"
        st["attempts"].append(rec); save()
        print(pg["id"], "t", n, rec["stage"], "OK" if st["state"] == "approved" else "FAIL", rec["problems"][:3], flush=True)
        if st["state"] == "approved":
            break
        corrections += rec["problems"]
    if st["state"] != "approved":
        st["state"] = "human_queue"; save()

# summary
att = sum(len(s["attempts"]) for s in state.values())
approved = [k for k, s in state.items() if s["state"] == "approved"]
res = {"pages": len(state), "approved_count": len(approved), "human_queue": len(state) - len(approved),
       "images_generated": att, "estimated_cost_usd": round(att * IMG_COST, 3),
       "approved_first_try": sum(1 for s in state.values() if s["state"] == "approved" and len(s["attempts"]) == 1)}
json.dump(res, open(os.path.join(folder, "summary.json"), "w"), indent=1)
print("SUMMARY", json.dumps(res), flush=True)
