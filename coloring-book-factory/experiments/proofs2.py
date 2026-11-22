#!/usr/bin/env python3
"""Proofs 2: title in round, bouncy letters (reference 'Snuggle') + round uppercase subtitle.
Usage: proofs2.py FONTS_FOLDER ART.png OUTPUT.png. OFL 1.1 fonts only."""
import os, sys
from PIL import Image, ImageDraw, ImageFont

FT, ART, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DPI = 300
px = lambda p: int(round(p * DPI))
BACKGROUND, BROWN, TERRACOTTA = (253, 240, 219), (92, 58, 40), (196, 120, 86)
W, H = px(8.625), px(8.75)
USABLE = W - px(0.125) - 2 * px(0.25) - px(0.3)  # maximum title width inside the safe zone
art = Image.open(ART).convert("RGB")


def F(path, size, axes=None):
    f = ImageFont.truetype(os.path.join(FT, path), size)
    if axes:
        f.set_variation_by_axes(axes)
    return f


ANG = [-6, 4, -3, 6, -4, 3, -5, 5, -2, 4, -6, 3, -4, 5]
DY = [0.00, -0.05, 0.03, -0.03, 0.05, -0.02, 0.04, -0.05, 0.02, -0.04, 0.03, -0.01, 0.05, -0.03]


def bouncy(img, text, mk, target, y, color, track=-0.03, bounce=True):
    """Letter by letter, rotated and shifted (hand-drawn effect). Size chosen by the actual
    ink height (target, in px) and limited by the usable width. y = top of the ink. Returns bottom of the ink."""
    size = 800
    d = ImageDraw.Draw(img)
    while True:
        f = mk(size)
        bb = f.getbbox(text)
        advs = [d.textlength(c, font=f) for c in text]
        tot = sum(advs) + track * size * (len(text) - 1) + 0.14 * size * text.count(' ')
        if (bb[3] - bb[1]) <= target and tot <= USABLE:
            break
        size -= 6
    x = (W - px(0.125) - tot) / 2
    for i, c in enumerate(text):
        if c != " ":
            pad = int(size * 0.4)
            lay = Image.new("RGBA", (int(advs[i]) + 2 * pad, int(size * 1.6) + 2 * pad), (0, 0, 0, 0))
            ImageDraw.Draw(lay).text((pad, pad - bb[1]), c, font=f, fill=color)
            if bounce:
                lay = lay.rotate(ANG[i % len(ANG)], resample=Image.BICUBIC, expand=False)
            dy = int(DY[i % len(DY)] * (bb[3] - bb[1])) if bounce else 0
            img.paste(lay, (int(x) - pad, y - pad + dy), lay)
        x += advs[i] + track * size + (0.14 * size if c == ' ' else 0)
    return y + (bb[3] - bb[1]) + int(0.06 * (bb[3] - bb[1]))


def subtitle(img, y, mk, size, color, track=0.06):
    d = ImageDraw.Draw(img)
    for ln in ["50 BOLD & EASY DESIGNS", "FOR ADULTS"]:
        f = mk(size)
        advs = [d.textlength(c, font=f) for c in ln]
        tot = sum(advs) + track * size * (len(ln) - 1)
        x = (W - px(0.125) - tot) / 2
        for c, a in zip(ln, advs):
            d.text((x, y), c, font=f, fill=color); x += a + track * size
        y += int(size * 1.1)
    return y


def base():
    im = Image.new("RGB", (W, H), BACKGROUND)
    side = px(5.3)
    im.paste(art.resize((side, side), Image.LANCZOS), ((W - px(0.125) - side) // 2, H - px(0.2) - side))
    return im


SUB_FREDOKA = lambda t: F("fredoka/Fredoka[wdth,wght].ttf", t, [600, 100])
TITLES = [
    ("DynaPuff", lambda t: F("dynapuff/DynaPuff[wdth,wght].ttf", t, [700, 100])),
    ("Sour Gummy", lambda t: F("sourgummy/SourGummy[wdth,wght].ttf", t, [125, 900])),
    ("Bagel Fat One", lambda t: F("bagelfatone/BagelFatOne-Regular.ttf", t)),
    ("Coiny", lambda t: F("coiny/Coiny-Regular.ttf", t)),
    ("Chango", lambda t: F("chango/Chango-Regular.ttf", t)),
    ("Rammetto One", lambda t: F("rammettoone/RammettoOne-Regular.ttf", t)),
    ("Mochiy Pop One", lambda t: F("mochiypopone/MochiyPopOne-Regular.ttf", t)),
    ("Cherry Bomb One", lambda t: F("cherrybombone/CherryBombOne-Regular.ttf", t)),
    ("Modak", lambda t: F("modak/Modak-Regular.ttf", t)),
]
SUBS = [
    ("A Fredoka", SUB_FREDOKA),
    ("B Nunito", lambda t: F("nunito/Nunito[wght].ttf", t, [900])),
    ("C Baloo 2", lambda t: F("baloo2/Baloo2[wght].ttf", t, [800])),
    ("D Varela Round", lambda t: F("varelaround/VarelaRound-Regular.ttf", t)),
    ("E Sour Gummy", lambda t: F("sourgummy/SourGummy[wdth,wght].ttf", t, [100, 700])),
]

th = 760; tw = int(W * th / H)
lab = F("nunito/Nunito[wght].ttf", 30, [800])
sub_height = 300
sheet = Image.new("RGB", (3 * tw + 80, 3 * (th + 50) + 70 + sub_height + 50), (235, 235, 235))
dd = ImageDraw.Draw(sheet)
for i, (name, mk) in enumerate(TITLES):
    im = base()
    y = bouncy(im, "COZY", mk, px(1.15), px(0.125) + px(0.4), BROWN)
    y = bouncy(im, "LITTLE CORNERS", mk, px(0.5), y + px(0.1), BROWN)
    subtitle(im, y + px(0.14), SUB_FREDOKA, 70, TERRACOTTA)
    x, yy = 20 + (i % 3) * (tw + 20), 20 + (i // 3) * (th + 50)
    dd.text((x, yy), f"{i + 1} {name}", font=lab, fill=(40, 40, 40))
    sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, yy + 40))
# subtitle strip
y0 = 20 + 3 * (th + 50) + 10
dd.text((20, y0), "Subtitle (uppercase paragraph):", font=lab, fill=(40, 40, 40))
bw = (3 * tw + 40 - 4 * 20) // 5
for j, (name, mk) in enumerate(SUBS):
    box = Image.new("RGB", (bw * 3, sub_height * 3), BACKGROUND)
    d = ImageDraw.Draw(box)
    yy = 70
    for ln in ["50 BOLD & EASY DESIGNS", "FOR ADULTS"]:
        f = mk(92)
        w = sum(d.textlength(c, font=f) for c in ln) + 0.06 * 92 * (len(ln) - 1)
        x = (bw * 3 - w) / 2
        for c in ln:
            d.text((x, yy), c, font=f, fill=BROWN); x += d.textlength(c, font=f) + 0.06 * 92
        yy += 120
    d.text((30, sub_height * 3 - 110), name, font=F("nunito/Nunito[wght].ttf", 60, [800]), fill=(150, 150, 150))
    sheet.paste(box.resize((bw, sub_height), Image.LANCZOS), (20 + j * (bw + 20), y0 + 45))
sheet.save(OUT)
print("ok", sheet.size)
