#!/usr/bin/env python3
"""Proofs 3: title closer to the 'Snuggle' reference.
Differences applied: letters packed together (negative tracking), bigger rotation, each letter with its own size
and height, mustard color with outline, 4-point little stars. OFL 1.1 fonts only.
Usage: proofs3.py FONTS_FOLDER ART.png OUTPUT.png"""
import math, os, sys
from PIL import Image, ImageDraw, ImageFont

FT, ART, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DPI = 300
px = lambda p: int(round(p * DPI))
BACKGROUND, BROWN, TERRACOTTA, MUSTARD = (253, 240, 219), (92, 58, 40), (196, 120, 86), (240, 190, 80)
W, H = px(8.625), px(8.75)
USABLE = W - px(0.125) - 2 * px(0.25) - px(0.3)
art = Image.open(ART).convert("RGB")

ANG = [-10, 7, -5, 9, -8, 6, -4, 8, -9, 5, -7, 9, -6, 7]
DY = [0.06, -0.08, 0.04, -0.05, 0.08, -0.06, 0.03, -0.08, 0.06, -0.03, 0.07, -0.06, 0.04, -0.07]
SC = [1.12, 0.94, 1.04, 0.96, 1.08, 0.95, 1.03, 0.97, 1.1, 0.94, 1.05, 0.98, 1.07, 0.95]


def F(path, size, axes=None):
    f = ImageFont.truetype(os.path.join(FT, path), max(8, int(size)))
    if axes:
        f.set_variation_by_axes(axes)
    return f


def letters(img, text, mk, target, y, color, outline=None, shadow=None, track=-0.09, strength=1.0):
    """Each letter: its own size, angle and height; letters almost touching. y = top; returns bottom."""
    d = ImageDraw.Draw(img)
    size = 900
    while True:
        fs = [mk(size * (SC[i % len(SC)] if c != " " else 1)) for i, c in enumerate(text)]
        advs = [d.textlength(c, font=f) for c, f in zip(text, fs)]
        spaces = [0.12 * size if c == " " else 0 for c in text]
        tot = sum(advs) + track * size * (len(text) - 1) + sum(spaces)
        alt = mk(size).getbbox(text.replace(" ", ""))
        if (alt[3] - alt[1]) <= target and tot <= USABLE:
            break
        size -= 8
    asc = mk(size).getmetrics()[0]
    top_ref = alt[1]
    x = (W - px(0.125) - tot) / 2
    s = int(size * 0.045) if outline else 0
    for i, (c, f) in enumerate(zip(text, fs)):
        if c != " ":
            pad = int(size * 0.5)
            lay = Image.new("RGBA", (int(advs[i]) + 2 * pad, int(size * 1.4) + 2 * pad), (0, 0, 0, 0))
            dl = ImageDraw.Draw(lay)
            base = pad + asc
            if shadow:
                dl.text((pad + shadow[0], base + shadow[1]), c, font=f, fill=shadow[2], anchor="ls",
                        stroke_width=s, stroke_fill=shadow[2])
            dl.text((pad, base), c, font=f, fill=color, anchor="ls", stroke_width=s, stroke_fill=outline)
            lay = lay.rotate(ANG[i % len(ANG)] * strength, resample=Image.BICUBIC, expand=False)
            dy = int(DY[i % len(DY)] * strength * (alt[3] - alt[1]))
            img.paste(lay, (int(x) - pad, y - pad - top_ref + dy), lay)
        x += advs[i] + track * size + spaces[i]
    return y + (alt[3] - alt[1]) + int(0.1 * (alt[3] - alt[1]))


def star(d, cx, cy, r, color):
    pts = []
    for k in range(8):
        a = math.pi / 4 * k - math.pi / 2
        rr = r if k % 2 == 0 else r * 0.32
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=color)


def subtitle(img, y, color):
    d = ImageDraw.Draw(img)
    f = F("fredoka/Fredoka[wdth,wght].ttf", 84, [600, 100])
    for ln in ["50 BOLD & EASY DESIGNS", "FOR ADULTS"]:
        w = sum(d.textlength(c, font=f) for c in ln) + 0.05 * 84 * (len(ln) - 1)
        x = (W - px(0.125) - w) / 2
        for c in ln:
            d.text((x, y), c, font=f, fill=color); x += d.textlength(c, font=f) + 0.05 * 84
        y += 96


def base():
    im = Image.new("RGB", (W, H), BACKGROUND)
    side = px(5.2)
    im.paste(art.resize((side, side), Image.LANCZOS), ((W - px(0.125) - side) // 2, H - px(0.2) - side))
    return im


FONTS = [
    ("DynaPuff", lambda t: F("dynapuff/DynaPuff[wdth,wght].ttf", t, [700, 100])),
    ("Bagel Fat One", lambda t: F("bagelfatone/BagelFatOne-Regular.ttf", t)),
    ("Cherry Bomb One", lambda t: F("cherrybombone/CherryBombOne-Regular.ttf", t)),
    ("Sour Gummy", lambda t: F("sourgummy/SourGummy[wdth,wght].ttf", t, [125, 900])),
]
COLORS = [
    ("brown", dict(color=BROWN, outline=None, shadow=None), MUSTARD),
    ("mustard + outline", dict(color=MUSTARD, outline=BROWN, shadow=(0, 22, BROWN)), TERRACOTTA),
]

th = 760; tw = int(W * th / H)
lab = F("nunito/Nunito[wght].ttf", 30, [800])
sheet = Image.new("RGB", (4 * tw + 100, 2 * (th + 50) + 30), (235, 235, 235))
dd = ImageDraw.Draw(sheet)
n = 0
for j, (cname, cfg, cstar) in enumerate(COLORS):
    for i, (fname, mk) in enumerate(FONTS):
        n += 1
        im = base()
        y = letters(im, "COZY", mk, px(1.25), px(0.125) + px(0.45), **cfg)
        y = letters(im, "LITTLE CORNERS", mk, px(0.55), y + px(0.05), strength=0.6, **cfg)
        subtitle(im, y + px(0.12), TERRACOTTA if j == 0 else BROWN)
        d = ImageDraw.Draw(im)
        for (ex, ey, r) in [(0.13, 0.07, 70), (0.86, 0.1, 55), (0.9, 0.2, 35), (0.1, 0.19, 40)]:
            star(d, ex * (W - px(0.125)), ey * H, r, cstar)
        x, yy = 20 + i * (tw + 20), 20 + j * (th + 50)
        dd.text((x, yy), f"{n} {fname}, {cname}", font=lab, fill=(40, 40, 40))
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, yy + 40))
sheet.save(OUT)
print("ok", sheet.size)
