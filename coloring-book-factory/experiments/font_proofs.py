#!/usr/bin/env python3
"""Typography proof sheet on the front of cover A (cream). OFL 1.1 fonts only, in ~/books/fonts."""
import os, sys
from PIL import Image, ImageDraw, ImageFont

DPI = 300
px = lambda p: int(round(p * DPI))
FT = os.path.expanduser("~/books/fonts")
art = Image.open(sys.argv[1]).convert("RGB")
out = sys.argv[2]
BACKGROUND, BROWN, TERRACOTTA, CREAM, WHITE = (253, 240, 219), (92, 58, 40), (196, 120, 86), (255, 248, 236), (255, 255, 255)
W, H = px(8.625), px(8.75)  # front with outer, top and bottom bleed
SAFE = px(0.25)


def F(path, size, axes=None):
    f = ImageFont.truetype(os.path.join(FT, path), size)
    if axes:
        f.set_variation_by_axes(axes)
    return f


def measure(d, t, f, s, track):
    if not track:
        b = d.textbbox((0, 0), t, font=f, stroke_width=s); return b[2] - b[0], b
    w = sum(d.textlength(c, font=f) for c in t) + track * (len(t) - 1) + 2 * s
    b = d.textbbox((0, 0), t, font=f, stroke_width=s)
    return int(w), b


def line(img, y, t, f, color, s=0, scolor=None, shadow=None, track=0, maxw=None):
    """Draws a centered line (within 0.25 in); shrinks it if it goes past maxw. Returns the bottom y."""
    d = ImageDraw.Draw(img)
    maxw = maxw or (W - px(0.125) - 2 * SAFE)  # usable zone: trim to trim minus 0.25 in
    while measure(d, t, f, s, track)[0] > maxw:
        f = f.font_variant(size=f.size - 4)
    w, b = measure(d, t, f, s, track)
    x0 = (W - px(0.125) - w) // 2  # centered on the trim (the outer bleed is on the right)
    layers = []
    if shadow:
        layers.append((shadow[0], shadow[1], shadow[2]))
    layers.append((0, 0, color))
    for dx, dy, c in layers:
        if track:
            x = x0 + s
            for ch in t:
                d.text((x + dx, y - b[1] + dy), ch, font=f, fill=c, stroke_width=s, stroke_fill=scolor if c == color else c)
                x += d.textlength(ch, font=f) + track
        else:
            d.text((x0 - b[0] + dx, y - b[1] + dy), t, font=f, fill=c, stroke_width=s, stroke_fill=scolor if c == color else c)
    return y + (b[3] - b[1])


def base():
    im = Image.new("RGB", (W, H), BACKGROUND)
    side = px(6.65)
    im.paste(art.resize((side, side), Image.LANCZOS), ((W - px(0.125) - side) // 2, H - px(0.225) - side))
    return im


SUB = "50 Bold & Easy Designs for Adults"
fsub = lambda size=78: F("nunito/Nunito[wght].ttf", size, [800])
y0 = px(0.125) + px(0.35)
proofs = []

def p1(im):  # current
    y = line(im, y0, "Cozy Little Corners", F("cherrybombone/CherryBombOne-Regular.ttf", 246), BROWN)
    line(im, y + px(0.12), SUB, fsub(), TERRACOTTA)
proofs.append(("1 Current: Cherry Bomb One", p1))

def p2(im):
    y = line(im, y0, "Cozy", F("caprasimo/Caprasimo-Regular.ttf", 420), BROWN, s=12, scolor=CREAM, shadow=(14, 14, TERRACOTTA))
    y = line(im, y + px(0.02), "Little Corners", F("caprasimo/Caprasimo-Regular.ttf", 200), BROWN, s=10, scolor=CREAM, shadow=(10, 10, TERRACOTTA))
    line(im, y + px(0.1), SUB, fsub(66), TERRACOTTA)
proofs.append(("2 Caprasimo, stacked, shadow", p2))

def p3(im):
    y = line(im, y0, "Cozy Little Corners", F("shrikhand/Shrikhand-Regular.ttf", 240), TERRACOTTA, shadow=(12, 12, BROWN))
    line(im, y + px(0.14), SUB, fsub(), BROWN)
proofs.append(("3 Shrikhand, retro", p3))

def p4(im):
    f = lambda t: F("dynapuff/DynaPuff[wdth,wght].ttf", t, [700, 100])
    y = line(im, y0, "Cozy", f(400), BROWN, s=22, scolor=WHITE)
    y = line(im, y - px(0.02), "Little Corners", f(210), BROWN, s=18, scolor=WHITE)
    line(im, y + px(0.1), SUB, fsub(66), TERRACOTTA)
proofs.append(("4 DynaPuff, sticker", p4))

def p5(im):
    f = lambda t: F("titanone/TitanOne-Regular.ttf", t)
    y = line(im, y0, "COZY", f(380), TERRACOTTA, track=20, shadow=(0, 14, BROWN))
    y = line(im, y + px(0.04), "LITTLE CORNERS", f(170), BROWN, track=14)
    line(im, y + px(0.12), SUB, fsub(66), TERRACOTTA)
proofs.append(("5 Titan One, uppercase", p5))

def p6(im):
    f = lambda t: F("bagelfatone/BagelFatOne-Regular.ttf", t)
    y = line(im, y0, "Cozy", f(400), TERRACOTTA, s=12, scolor=BROWN)
    y = line(im, y + px(0.02), "Little Corners", f(200), TERRACOTTA, s=9, scolor=BROWN)
    line(im, y + px(0.1), SUB, fsub(66), BROWN)
proofs.append(("6 Bagel Fat One, outline", p6))

def p7(im):
    y = line(im, y0 - px(0.1), "Cozy", F("pacifico/Pacifico-Regular.ttf", 400), TERRACOTTA)
    y = line(im, y - px(0.05), "LITTLE CORNERS", F("fredoka/Fredoka[wdth,wght].ttf", 170, [600, 100]), BROWN, track=24)
    line(im, y + px(0.12), SUB, fsub(66), TERRACOTTA)
proofs.append(("7 Pacifico + Fredoka", p7))

def p8(im):
    y = line(im, y0, "Cozy Little", F("youngserif/YoungSerif-Regular.ttf", 230), BROWN)
    y = line(im, y + px(0.02), "Corners", F("youngserif/YoungSerif-Regular.ttf", 230), BROWN)
    line(im, y + px(0.12), SUB.upper(), F("nunito/Nunito[wght].ttf", 54, [800]), TERRACOTTA, track=6)
proofs.append(("8 Young Serif, bookish", p8))

def p9(im):
    f = lambda t: F("gluten/Gluten[slnt,wght].ttf", t, [800, 0])
    y = line(im, y0, "Cozy Little", f(250), BROWN, shadow=(0, 10, TERRACOTTA))
    y = line(im, y - px(0.02), "Corners", f(250), BROWN, shadow=(0, 10, TERRACOTTA))
    line(im, y + px(0.1), SUB, fsub(66), TERRACOTTA)
proofs.append(("9 Gluten, hand-drawn", p9))

th = 760
tw = int(W * th / H)
lab = F("nunito/Nunito[wght].ttf", 30, [800])
sheet = Image.new("RGB", (3 * tw + 80, 3 * (th + 50) + 30), (235, 235, 235))
for i, (name, fn) in enumerate(proofs):
    im = base(); fn(im)
    x, y = 20 + (i % 3) * (tw + 20), 20 + (i // 3) * (th + 50)
    ImageDraw.Draw(sheet).text((x, y), name, font=lab, fill=(40, 40, 40))
    sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 40))
sheet.save(out)
print("ok", sheet.size)
