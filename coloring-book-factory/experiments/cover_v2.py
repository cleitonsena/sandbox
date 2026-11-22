#!/usr/bin/env python3
"""Cover v2: 3 design variations for the board to choose from (2026-11-21).

Usage: cover_v2.py BOOK_FOLDER N_PAGES
Reads FOLDER/kit/variations/art-{a,b,c}.png and writes cover-{a,b,c}.pdf + preview.
Same KDP rules as assemble.py (bleed 0.125; spine N x 0.002252; spine text only with 80+;
text >= 0.25 in inside the trim; white barcode area 2 x 1.2 in).
Fonts: only OFL 1.1 in ~/books/fonts (license checked in each one's OFL.txt).
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

DPI, TRIM, BLEED, IN_PER_PAGE = 300, 8.5, 0.125, 0.002252
px = lambda inches: int(round(inches * DPI))
FT = os.path.expanduser("~/books/fonts")


def font(name, size, axes=None):
    paths = {
        "cherry": "cherrybombone/CherryBombOne-Regular.ttf",
        "lilita": "lilitaone/LilitaOne-Regular.ttf",
        "fraunces": "fraunces/Fraunces[SOFT,WONK,opsz,wght].ttf",
        "nunito": "nunito/Nunito[wght].ttf",
    }
    f = ImageFont.truetype(os.path.join(FT, paths[name]), size)
    if axes:
        f.set_variation_by_axes(axes)
    return f


def width(d, t, f, s=0):
    b = d.textbbox((0, 0), t, font=f, stroke_width=s)
    return b[2] - b[0]


VAR = {
    "a": dict(name="Cream, rounded title", background=(253, 240, 219), spine=(196, 120, 86),
              title=("cherry", None), title_color=(92, 58, 40), title_stroke=None,
              sub_color=(196, 120, 86), text=(92, 58, 40), spine_text=(255, 248, 240), art="vignette"),
    "b": dict(name="Night, block title", background=(57, 39, 56), spine=(247, 196, 107),
              title=("lilita", None), title_color=(255, 236, 200), title_stroke=(30, 20, 30),
              sub_color=(247, 196, 107), text=(255, 236, 200), spine_text=(57, 39, 56), art="vignette"),
    "c": dict(name="Full art, soft serif", background=(251, 227, 151), spine=(92, 58, 40),
              title=("fraunces", [72, 800, 100, 0]), title_color=(92, 58, 40), title_stroke=None,
              sub_color=(179, 93, 30), text=(92, 58, 40), spine_text=(251, 227, 151), art="full"),
}

folder = os.path.abspath(sys.argv[1])
n = int(sys.argv[2])
book = json.load(open(os.path.join(folder, "book.json")))
state = json.load(open(os.path.join(folder, "state.json")))
vdir = os.path.join(folder, "kit", "variations")
samples = [state[p["id"]]["attempts"][-1]["file"] for p in book["pages"]
           if state.get(p["id"], {}).get("state") == "approved"][:4]

spine = n * IN_PER_PAGE
W, H = px(BLEED + TRIM + spine + TRIM + BLEED), px(BLEED + TRIM + BLEED)
xl0, xl1 = px(BLEED + TRIM), px(BLEED + TRIM + spine)
safe = px(0.25)
res = {}

for k, v in VAR.items():
    cover = Image.new("RGB", (W, H), v["background"])
    d = ImageDraw.Draw(cover)
    art = Image.open(os.path.join(vdir, f"art-{k}.png")).convert("RGB")
    front_width = W - xl1  # from the spine to the outer bleed
    # --- front art ---
    if v["art"] == "full":
        side = max(front_width, H)
        a = art.resize((side, side), Image.LANCZOS)
        a = a.crop(((side - front_width) // 2, (side - H) // 2, (side - front_width) // 2 + front_width, (side - H) // 2 + H))
        cover.paste(a, (xl1, 0))
        art_ppi = round(art.width / (side / DPI))
    else:
        side = px(6.65)
        a = art.resize((side, side), Image.LANCZOS)
        cover.paste(a, (xl1 + (px(TRIM) - side) // 2, H - px(BLEED) - px(0.1) - side))
        art_ppi = round(art.width / (side / DPI))
    # --- title and subtitle (front) ---
    cx0, cx1 = xl1 + safe, xl1 + px(TRIM) - safe
    st = 10 if v["title_stroke"] else 0
    size = 300
    while True:
        ft = font(v["title"][0], size, v["title"][1])
        if width(d, book["title"], ft, st) <= (cx1 - cx0) - px(0.3):
            break
        size -= 6
    tw = width(d, book["title"], ft, st)
    y_title = px(BLEED) + px(0.4)
    d.text((cx0 + ((cx1 - cx0) - tw) // 2, y_title), book["title"], font=ft, fill=v["title_color"],
           stroke_width=st, stroke_fill=v["title_stroke"])
    title_bottom = d.textbbox((0, y_title), book["title"], font=ft, stroke_width=st)[3]
    sub = "50 Bold & Easy Designs for Adults"
    fs = font("nunito", 78, [800])
    sw = width(d, sub, fs)
    d.text((cx0 + ((cx1 - cx0) - sw) // 2, title_bottom + px(0.12)), sub, font=fs, fill=v["sub_color"])
    # --- back cover ---
    xb = px(BLEED)
    fb = font("nunito", 54, [600])
    fbb = font("nunito", 58, [800])
    y = px(BLEED) + px(0.75)
    blurb = book["back_cover"][:2]
    for i, par in enumerate(blurb):
        f_ = fbb if i == 0 else fb
        lines, cur = [], ""
        for p in par.split():
            t = (cur + " " + p).strip()
            if width(d, t, f_) <= px(TRIM) - 2 * px(0.8):
                cur = t
            else:
                lines.append(cur); cur = p
        lines.append(cur)
        for ln in lines:
            d.text((xb + (px(TRIM) - width(d, ln, f_)) // 2, y), ln, font=f_, fill=v["text"]); y += 80
        y += 50
    thumb, gap = px(1.7), px(0.2)
    tot = len(samples) * thumb + (len(samples) - 1) * gap
    mx, my = xb + (px(TRIM) - tot) // 2, y + px(0.15)
    for s in samples:
        m = Image.open(s).convert("RGB").resize((thumb, thumb), Image.LANCZOS)
        d.rounded_rectangle([mx - 10, my - 10, mx + thumb + 10, my + thumb + 10], radius=24, fill=(255, 255, 255))
        cover.paste(m, (mx, my)); mx += thumb + gap
    y = my + thumb + px(0.35)
    for ln in ["Single-sided pages, so markers never ruin the next design", "Large, simple shapes for relaxing, easy coloring"]:
        f_ = font("nunito", 50, [700])
        d.text((xb + (px(TRIM) - width(d, ln, f_)) // 2, y), ln, font=f_, fill=v["text"]); y += 72
    # barcode: white 2 x 1.2 in, 0.25 in from the spine and the bottom trim
    bx1 = xl0 - px(0.25); by1 = px(BLEED + TRIM) - px(0.25)
    d.rectangle([bx1 - px(2.0), by1 - px(1.2), bx1, by1], fill=(255, 255, 255))
    # --- spine ---
    d.rectangle([xl0, 0, xl1, H], fill=v["spine"])
    if n >= 80:
        clearance = px(0.0625)
        alt = (xl1 - xl0) - 2 * clearance
        fsp = font(v["title"][0], max(10, int(alt * 0.85)), v["title"][1])
        txt = book["title"].upper()
        bb = d.textbbox((0, 0), txt, font=fsp)
        strip = Image.new("RGBA", (bb[2] - bb[0] + 4, bb[3] - bb[1] + 4), (0, 0, 0, 0))
        ImageDraw.Draw(strip).text((-bb[0] + 2, -bb[1] + 2), txt, font=fsp, fill=v["spine_text"])
        strip = strip.rotate(-90, expand=True)
        cover.paste(strip, (xl0 + ((xl1 - xl0) - strip.width) // 2, (H - strip.height) // 2), strip)
    cover.save(os.path.join(vdir, f"cover-{k}.pdf"), resolution=DPI)
    cover.save(os.path.join(vdir, f"cover-{k}-preview.png"))
    res[k] = {"name": v["name"], "title_size_pt": size, "effective_art_ppi": art_ppi}

# comparison sheet
th = 700
sheet = Image.new("RGB", (int(W * th / H) + 40, 3 * th + 80), (120, 120, 120))
for i, k in enumerate("abc"):
    im = Image.open(os.path.join(vdir, f"cover-{k}-preview.png"))
    sheet.paste(im.resize((int(W * th / H), th)), (20, 20 + i * (th + 20)))
sheet.save(os.path.join(vdir, "compare-covers.png"))
print(json.dumps({"spine_in": round(spine, 4), "px": [W, H], "variations": res}))
