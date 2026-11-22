#!/usr/bin/env python3
"""Final cover v3 (board choice 2026-11-21): cream cover A + title 7 (Cherry Bomb One mustard,
brown outline, shadow, bouncy letters) + uppercase Fredoka subtitle + little stars.
Usage: final_cover.py FONTS_FOLDER ART.png N_PAGES OUTPUT_WITHOUT_EXTENSION THUMB1.png THUMB2.png ...
KDP rules (read 2026-11-21): bleed 0.125; spine N x 0.002252 (white paper); spine text only with 80+
pages, clearance 0.0625; text >= 0.25 in from the trim; white barcode area 2 x 1.2 in at 0.25 in
from the spine and the trim. OFL 1.1 fonts only."""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFont

FT, ART, N, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
THUMBS = sys.argv[5:]
# texts come from book.json["cover"] (env BOOK_JSON); omitted = pilot Cozy Little Corners
_C = json.load(open(os.environ["BOOK_JSON"])).get("cover", {}) if os.environ.get("BOOK_JSON") else {}
TXT = dict(title1="COZY", title2="LITTLE CORNERS", sub=["50 BOLD & EASY DESIGNS", "FOR ADULTS"],
           back_title="SLOW DOWN AND COLOR", back_subtitle="50 cozy little corners to fill with color",
           blurb=("Bold lines and big, simple shapes make every page relaxing and easy to finish "
                  "with markers, colored pencils or gel pens."),
           bullets=["Single-sided pages, so markers never ruin the next design",
                    "Large, simple shapes for relaxing, easy coloring", "Square 8.5 x 8.5 in format"],
           spine="COZY LITTLE CORNERS")
TXT.update(_C)
DPI, TRIM, BLEED, IN_PER_PAGE = 300, 8.5, 0.125, 0.002252
px = lambda p: int(round(p * DPI))
BACKGROUND, BROWN, TERRACOTTA, MUSTARD = (253, 240, 219), (92, 58, 40), (196, 120, 86), (240, 190, 80)
# "full_bleed" mode (cover v4, board 2026-11-22): art up to the edge, white DynaPuff title with outline
FULL_BLEED = TXT.get("mode") == "full_bleed"
if FULL_BLEED:
    BACKGROUND = tuple(TXT.get("background_color", (222, 238, 252)))  # back cover
    BROWN = tuple(TXT.get("outline_color", (31, 58, 95)))             # outline, texts, spine
    TERRACOTTA = tuple(TXT.get("accent_color", (240, 140, 50)))       # stars
    MUSTARD = (255, 255, 255)                                          # title letters
SAFE = px(0.25)

ANG = [-10, 7, -5, 9, -8, 6, -4, 8, -9, 5, -7, 9, -6, 7]
DY = [0.06, -0.08, 0.04, -0.05, 0.08, -0.06, 0.03, -0.08, 0.06, -0.03, 0.07, -0.06, 0.04, -0.07]
SC = [1.12, 0.94, 1.04, 0.96, 1.08, 0.95, 1.03, 0.97, 1.1, 0.94, 1.05, 0.98, 1.07, 0.95]


def F(path, size, axes=None):
    f = ImageFont.truetype(os.path.join(FT, path), max(8, int(size)))
    if axes:
        f.set_variation_by_axes(axes)
    return f


TITLE = (lambda t: F("dynapuff/DynaPuff[wdth,wght].ttf", t, [700, 100])) if FULL_BLEED else \
    (lambda t: F("cherrybombone/CherryBombOne-Regular.ttf", t))
SUBF = lambda t: F("fredoka/Fredoka[wdth,wght].ttf", t, [600, 100])
BODY = lambda t, w=600: F("nunito/Nunito[wght].ttf", t, [w])


def letters(img, x0, x1, text, target, y, strength=1.0, track=-0.07):
    """Bouncy title centered between x0 and x1. Returns (bottom of the ink, actual box occupied)."""
    d = ImageDraw.Draw(img)
    usable = (x1 - x0) - px(0.2)
    size = 900
    while True:
        fs = [TITLE(size * (SC[i % len(SC)] if c != " " else 1)) for i, c in enumerate(text)]
        advs = [d.textlength(c, font=f) for c, f in zip(text, fs)]
        spaces = [0.16 * size if c == " " else 0 for c in text]
        tot = sum(advs) + track * size * (len(text) - 1) + sum(spaces)
        alt = TITLE(size).getbbox(text.replace(" ", ""))
        if (alt[3] - alt[1]) <= target and tot <= usable:
            break
        size -= 8
    asc = TITLE(size).getmetrics()[0]
    x = x0 + ((x1 - x0) - tot) / 2
    s = int(size * (0.07 if FULL_BLEED else 0.045))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    for i, (c, f) in enumerate(zip(text, fs)):
        if c != " ":
            pad = int(size * 0.5)
            lay = Image.new("RGBA", (int(advs[i]) + 2 * pad, int(size * 1.4) + 2 * pad), (0, 0, 0, 0))
            dl = ImageDraw.Draw(lay)
            base = pad + asc
            dl.text((pad, base + int(size * 0.06)), c, font=f, fill=BROWN, anchor="ls", stroke_width=s, stroke_fill=BROWN)
            dl.text((pad, base), c, font=f, fill=MUSTARD, anchor="ls", stroke_width=s, stroke_fill=BROWN)
            lay = lay.rotate(ANG[i % len(ANG)] * strength, resample=Image.BICUBIC, expand=False)
            dy = int(DY[i % len(DY)] * strength * (alt[3] - alt[1]))
            layer.alpha_composite(lay, (int(x) - pad, y - pad - alt[1] + dy))
        x += advs[i] + track * size + spaces[i]
    img.paste(layer, (0, 0), layer)
    return y + (alt[3] - alt[1]) + int(0.1 * (alt[3] - alt[1])), layer.getbbox()


def centered(d, x0, x1, y, txt, f, color, track=0.0):
    w = sum(d.textlength(c, font=f) for c in txt) + track * f.size * (len(txt) - 1)
    x = x0 + ((x1 - x0) - w) / 2
    for c in txt:
        d.text((x, y), c, font=f, fill=color); x += d.textlength(c, font=f) + track * f.size


def star(d, cx, cy, r, color):
    d.polygon([(cx + (r if k % 2 == 0 else r * 0.32) * math.cos(math.pi / 4 * k - math.pi / 2),
                cy + (r if k % 2 == 0 else r * 0.32) * math.sin(math.pi / 4 * k - math.pi / 2)) for k in range(8)], fill=color)


spine = N * IN_PER_PAGE
W, H = px(BLEED + TRIM + spine + TRIM + BLEED), px(BLEED + TRIM + BLEED)
xl0, xl1 = px(BLEED + TRIM), px(BLEED + TRIM + spine)
cover = Image.new("RGB", (W, H), BACKGROUND)
d = ImageDraw.Draw(cover)

# ---------- front ----------
fx0, fx1 = xl1 + SAFE, xl1 + px(TRIM) - SAFE  # front safe zone
art = Image.open(ART).convert("RGB")
if FULL_BLEED:
    # square art up to the edge: covers front + bleed (W - xl1) x H, centered horizontally
    lf = W - xl1
    a = art.resize((max(lf, H), max(lf, H)), Image.LANCZOS)
    cover.paste(a.crop(((a.width - lf) // 2, (a.height - H) // 2, (a.width - lf) // 2 + lf, (a.height - H) // 2 + H)), (xl1, 0))
    if min(art.size) < 0.95 * max(lf, H):
        print(f"WARNING: art {art.size} below {max(lf, H)} px (less than 300 ppi)", file=sys.stderr)
    m = px(0.2)  # extra clearance: thick outline and rotated letters
    y, cx1 = letters(cover, fx0 + m, fx1 - m, TXT["title1"], px(1.3), px(BLEED) + px(0.5), strength=0.7, track=-0.05)
    y, cx2 = letters(cover, fx0 + m, fx1 - m, TXT["title2"], px(0.6), y + px(0.02), strength=0.42, track=-0.05)
    fs = SUBF(70)
    txt = " ".join(TXT["sub"])
    w = d.textlength(txt, font=fs)
    x = xl1 + (px(TRIM) - w) / 2; ys = y + px(0.1)
    d.rounded_rectangle([x - 40, ys - 14, x + w + 40, ys + 86], radius=50, fill=(255, 255, 255))
    d.text((x, ys), txt, font=fs, fill=BROWN)
else:
    side = px(5.2)
    from PIL import ImageFilter
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rectangle([int(side * 0.03)] * 2 + [side - int(side * 0.03)] * 2, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(side * 0.012))  # soft edge: the art blends into the background
    cover.paste(art.resize((side, side), Image.LANCZOS), (xl1 + (px(TRIM) - side) // 2, H - px(BLEED) - px(0.1) - side), mask)
    y, cx1 = letters(cover, fx0, fx1, TXT["title1"], px(1.25), px(BLEED) + px(0.45))
    y, cx2 = letters(cover, fx0, fx1, TXT["title2"], px(0.55), y + px(0.05), strength=0.6, track=-0.05)
    ys = y + px(0.12)
    for ln in TXT["sub"]:
        centered(d, xl1, xl1 + px(TRIM), ys, ln, SUBF(84), BROWN, 0.05); ys += 96
    for ex, ey, r in [(0.12, 0.07, 70), (0.87, 0.1, 55), (0.91, 0.2, 35), (0.09, 0.19, 40)]:
        star(d, xl1 + ex * px(TRIM), ey * H, r, TERRACOTTA)

# ---------- back cover ----------
bx0, bx1 = px(BLEED), px(BLEED + TRIM)
y = px(BLEED) + px(0.7)
centered(d, bx0, bx1, y, TXT["back_title"], SUBF(96), BROWN, 0.05); y += 120
centered(d, bx0, bx1, y, TXT["back_subtitle"], BODY(56, 700), TERRACOTTA); y += 110
text = TXT["blurb"]
f = BODY(52)
lines, cur = [], ""
for p in text.split():
    t = (cur + " " + p).strip()
    if d.textlength(t, font=f) <= px(TRIM) - 2 * px(0.9): cur = t
    else: lines.append(cur); cur = p
lines.append(cur)
for l in lines:
    centered(d, bx0, bx1, y, l, f, BROWN); y += 74
thumb, gap = px(1.7), px(0.2)
tot = len(THUMBS) * thumb + (len(THUMBS) - 1) * gap
mx, my = bx0 + (px(TRIM) - tot) // 2, y + px(0.25)
for i, s in enumerate(THUMBS):
    m = Image.open(s).convert("RGB")
    mg = int(m.width * 0.375 / 8.5)  # removes the page's white margin
    m = m.crop((mg, mg, m.width - mg, m.height - mg)).resize((thumb, thumb), Image.LANCZOS)
    d.rounded_rectangle([mx - 12, my - 12, mx + thumb + 12, my + thumb + 12], radius=26, fill=(255, 255, 255), outline=BROWN, width=5)
    cover.paste(m, (mx, my)); mx += thumb + gap
y = my + thumb + px(0.4)
for txt in TXT["bullets"]:
    fb = BODY(50, 700)
    w = d.textlength(txt, font=fb)
    x = bx0 + (px(TRIM) - w - 70) / 2
    star(d, x + 22, y + 30, 24, TERRACOTTA)
    d.text((x + 70, y), txt, font=fb, fill=BROWN); y += 78
# barcode: white 2 x 1.2 in, 0.25 in from the spine and the bottom trim
bb1 = xl0 - px(0.25); bby1 = px(BLEED + TRIM) - px(0.25)
barcode = [bb1 - px(2.0), bby1 - px(1.2), bb1, bby1]
d.rectangle(barcode, fill=(255, 255, 255))

# ---------- spine ----------
d.rectangle([xl0, 0, xl1, H], fill=BROWN)
if N >= 80:
    clearance = px(0.0625)
    alt = (xl1 - xl0) - 2 * clearance
    fsp = TITLE(int(alt * 0.85))
    txt = TXT["spine"]
    b = d.textbbox((0, 0), txt, font=fsp)
    strip = Image.new("RGBA", (b[2] - b[0] + 4, b[3] - b[1] + 4), (0, 0, 0, 0))
    ImageDraw.Draw(strip).text((-b[0] + 2, -b[1] + 2), txt, font=fsp, fill=MUSTARD)
    strip = strip.rotate(-90, expand=True)
    cover.paste(strip, (xl0 + ((xl1 - xl0) - strip.width) // 2, (H - strip.height) // 2), strip)

cover.save(OUT + "-preview.png", dpi=(DPI, DPI))
try:
    cover.save(OUT + ".pdf", resolution=DPI)
except KeyError:  # Pillow without JPEG (main Mac): PDF generated later with sips
    pass
front_safe = [fx0, px(BLEED) + SAFE, fx1, H - px(BLEED) - SAFE]
inside = lambda bx: bx[0] >= front_safe[0] and bx[2] <= front_safe[2] and bx[1] >= front_safe[1]
print(json.dumps({"spine_in": round(spine, 4), "size_in": [round(W / DPI, 4), round(H / DPI, 4)],
                  "title_inside_safe_zone": inside(cx1) and inside(cx2), "title_boxes": [list(cx1), list(cx2)], "safe_zone": front_safe,
                  "back_cover_bottom_px": y, "barcode_top_px": barcode[1],
                  "spine_text": N >= 80}))
