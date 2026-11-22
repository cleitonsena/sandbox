#!/usr/bin/env python3
"""Proofs 4: full-bleed cover (art up to the edge), white title with a dark outline.
Usage: cover_proofs4.py FONTS_FOLDER OUTPUT.png ART1 COLOR1 ART2 COLOR2 ART3 COLOR3 (COLOR = outline hex)"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

FT, OUT = sys.argv[1], sys.argv[2]
PAIRS = [(sys.argv[i], sys.argv[i + 1]) for i in range(3, len(sys.argv), 2)]
DPI = 300
px = lambda p: int(round(p * DPI))
W, H = px(8.625), px(8.75)
USABLE = W - px(0.125) - 2 * px(0.25) - px(0.3)
ANG = [-7, 5, -4, 6, -5, 4, -3, 6, -6, 4, -5, 6, -4, 5]
DY = [0.04, -0.05, 0.03, -0.04, 0.05, -0.04, 0.02, -0.05, 0.04, -0.02, 0.05, -0.04, 0.03, -0.05]
TITLE = lambda t: ImageFont.truetype(os.path.join(FT, "cherrybombone/CherryBombOne-Regular.ttf"), max(8, int(t)))
SUB = ImageFont.truetype(os.path.join(FT, "fredoka/Fredoka[wdth,wght].ttf"), 70)
SUB.set_variation_by_axes([600, 100])


def hexc(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def letters(img, text, target, y, outline, strength=1.0, track=-0.05):
    d = ImageDraw.Draw(img)
    size = 900
    while True:
        advs = [d.textlength(c, font=TITLE(size)) for c in text]
        tot = sum(advs) + track * size * (len(text) - 1) + 0.16 * size * text.count(" ")
        alt = TITLE(size).getbbox(text.replace(" ", ""))
        if (alt[3] - alt[1]) <= target and tot <= USABLE:
            break
        size -= 8
    f = TITLE(size); asc = f.getmetrics()[0]; s = int(size * 0.07)
    x = (W - px(0.125) - tot) / 2
    for i, c in enumerate(text):
        if c != " ":
            pad = int(size * 0.5)
            lay = Image.new("RGBA", (int(advs[i]) + 2 * pad, int(size * 1.4) + 2 * pad), (0, 0, 0, 0))
            dl = ImageDraw.Draw(lay)
            dl.text((pad, pad + asc + int(size * 0.07)), c, font=f, fill=outline, anchor="ls", stroke_width=s, stroke_fill=outline)
            dl.text((pad, pad + asc), c, font=f, fill=(255, 255, 255), anchor="ls", stroke_width=s, stroke_fill=outline)
            lay = lay.rotate(ANG[i % len(ANG)] * strength, resample=Image.BICUBIC)
            img.paste(lay, (int(x) - pad, y - pad - alt[1] + int(DY[i % len(DY)] * strength * (alt[3] - alt[1]))), lay)
        x += advs[i] + track * size + (0.16 * size if c == " " else 0)
    return y + (alt[3] - alt[1]) + int(0.12 * (alt[3] - alt[1]))


def band(img, y, txt, outline):
    d = ImageDraw.Draw(img)
    w = d.textlength(txt, font=SUB)
    x = (W - px(0.125) - w) / 2
    d.rounded_rectangle([x - 40, y - 14, x + w + 40, y + 86], radius=50, fill=(255, 255, 255))
    d.text((x, y), txt, font=SUB, fill=outline)


covers = []
for art, color in PAIRS:
    outline = hexc(color)
    im = Image.open(art).convert("RGB").resize((W, W)).crop((0, 0, W, H)) if False else Image.open(art).convert("RGB").resize((H, H), Image.LANCZOS).crop(((H - W) // 2, 0, (H - W) // 2 + W, H))
    y = letters(im, "COZY", px(1.3), px(0.125) + px(0.35), outline)
    y = letters(im, "LITTLE CORNERS", px(0.6), y + px(0.02), outline, strength=0.6)
    band(im, y + px(0.1), "50 BOLD & EASY DESIGNS FOR ADULTS", outline)
    covers.append(im)
th = 700; tw = int(W * th / H); thumb = 260; mw = int(W * thumb / H)
sheet = Image.new("RGB", (len(covers) * (tw + 30) + 30, th + thumb + 110), (255, 255, 255))
d = ImageDraw.Draw(sheet)
lab = ImageFont.truetype(os.path.join(FT, "nunito/Nunito[wght].ttf"), 30)
for i, im in enumerate(covers):
    x = 30 + i * (tw + 30)
    d.text((x, 10), f"Proof {'ABC'[i]}", font=lab, fill=(0, 0, 0))
    sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, 50))
    d.text((x, th + 60), "size in search results:", font=lab, fill=(120, 120, 120))
    sheet.paste(im.resize((mw, thumb), Image.LANCZOS), (x, th + 100))
sheet.save(OUT)
print("ok", sheet.size)
