#!/usr/bin/env python3
"""Assembles the interior PDF and the cover PDF of a coloring book (KDP paperback, no bleed on the interior).

Usage:
  assemble.py interior FOLDER            -> FOLDER/kit/interior.pdf
  assemble.py cover FOLDER ART.png [N]   -> FOLDER/kit/cover.pdf (N = book pages; omitted = interior pages)

Rules (official KDP pages read on 2026-11-21: GVBQ3CMEQW3W2VL6, G201857950, G201953020, G5HDYGP4BXLX4RUW):
- Interior without bleed: page = trim 8.5 x 8.5 in. Minimum margins: inside 0.375 in (24-150 pages), the rest 0.25 in.
  We use 0.375 in on all sides.
- 300 dpi minimum. Cover: a single PDF (back cover + spine + front cover), bleed 0.125 in top, bottom and outside.
- Spine, white paper, black ink: pages x 0.002252 in. Spine text only with 79+ pages, 0.0625 in clearance.
- Cover text at least 0.25 in inside the trim. Barcode: white area 2 x 1.2 in,
  at least 0.25 in from the spine and the trim (KDP places the barcode if we do not provide one).
Publishes nothing: only generates files.
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

DPI = 300
TRIM = 8.5
MARGIN = 0.375
BLEED = 0.125
IN_PER_PAGE = 0.002252
F_TITLE = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
F_TEXT = "/System/Library/Fonts/Supplemental/Georgia.ttf"
F_TEXT_B = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
px = lambda inches: int(round(inches * DPI))

mode, folder = sys.argv[1], os.path.abspath(sys.argv[2])
book = json.load(open(os.path.join(folder, "book.json")))
state = json.load(open(os.path.join(folder, "state.json")))
kit = os.path.join(folder, "kit")
os.makedirs(kit, exist_ok=True)
side = px(TRIM)


def font(path, size):
    return ImageFont.truetype(path, size)


def centered_text(d, y, txt, f, width, color=0):
    w = d.textbbox((0, 0), txt, font=f)[2]
    d.text(((width - w) // 2, y), txt, font=f, fill=color)


def wrap(d, txt, f, max_width):
    lines, current = [], ""
    for p in txt.split():
        t = (current + " " + p).strip()
        if d.textbbox((0, 0), t, font=f)[2] <= max_width:
            current = t
        else:
            lines.append(current); current = p
    return lines + [current]


def image_page(src):
    usable = side - 2 * px(MARGIN)
    im = Image.open(src).convert("L").resize((usable, usable), Image.LANCZOS)
    canvas = Image.new("L", (side, side), 255)
    canvas.paste(im, (px(MARGIN), px(MARGIN)))
    return canvas.point(lambda v: 255 if v > 150 else 0).convert("1")


def approved():
    out = []
    for pg in book["pages"]:
        st = state.get(pg["id"], {})
        if st.get("state") == "approved":
            out.append(st["attempts"][-1]["file"])
    return out


if mode == "interior":
    pages = []
    # 1. title
    p = Image.new("L", (side, side), 255); d = ImageDraw.Draw(p)
    centered_text(d, px(3.0), book["title"], font(F_TITLE, 150), side)
    centered_text(d, px(3.8), book["subtitle"], font(F_TEXT, 60), side)
    pages.append(p)
    # 2. copyright and tip
    p = Image.new("L", (side, side), 255); d = ImageDraw.Draw(p)
    f = font(F_TEXT, 40)
    y = px(5.6)
    for par in book["copyright"]:
        for line in wrap(d, par, f, side - 2 * px(1.0)):
            centered_text(d, y, line, f, side); y += 56
        y += 40
    pages.append(p)
    # 3. coloring pages, each followed by a blank back (markers do not bleed into the next design)
    for src in approved():
        pages.append(image_page(src))
        pages.append(Image.new("1", (side, side), 1))
    dest = os.path.join(kit, "interior.pdf")
    pages[0].save(dest, save_all=True, append_images=pages[1:], resolution=DPI)
    json.dump({"interior_pages": len(pages)}, open(os.path.join(kit, "interior.json"), "w"))
    print(json.dumps({"interior": dest, "pages": len(pages), "kdp_minimum": 24}))

elif mode == "cover":
    art = sys.argv[3]
    n = int(sys.argv[4]) if len(sys.argv) > 4 else json.load(open(os.path.join(kit, "interior.json")))["interior_pages"]
    spine = n * IN_PER_PAGE
    W = px(BLEED + TRIM + spine + TRIM + BLEED)
    H = px(BLEED + TRIM + BLEED)
    background = tuple(book["background_color"])
    ink = tuple(book["text_color"])
    cover = Image.new("RGB", (W, H), background)
    d = ImageDraw.Draw(cover)
    x_spine0 = px(BLEED + TRIM)            # start of the spine
    x_spine1 = px(BLEED + TRIM + spine)    # end of the spine = start of the front cover
    x_front = x_spine1
    safe = px(0.25)
    # --- front cover ---
    panel = px(6.4)  # 1920 px at 300 dpi
    artwork = Image.open(art).convert("RGB").resize((panel, panel), Image.LANCZOS)
    cx = x_front + (px(TRIM) - panel) // 2
    top = px(BLEED) + px(1.75)
    d.rectangle([cx - 12, top - 12, cx + panel + 12, top + panel + 12], fill=(255, 255, 255))
    cover.paste(artwork, (cx, top))
    front_width = px(TRIM) - 2 * safe
    def front_center(y, txt, f):
        w = d.textbbox((0, 0), txt, font=f)[2]
        d.text((x_front + (px(TRIM) - w) // 2, y), txt, font=f, fill=ink)
    ft = font(F_TITLE, 170)
    while d.textbbox((0, 0), book["title"], font=ft)[2] > front_width:
        ft = font(F_TITLE, ft.size - 6)
    front_center(px(BLEED) + px(0.45), book["title"], ft)
    front_center(px(BLEED) + px(1.2), book["subtitle"], font(F_TEXT_B, 64))
    # --- back cover ---
    x_back = px(BLEED)
    f = font(F_TEXT, 52)
    y = px(BLEED) + px(0.9)
    for par in book["back_cover"]:
        for line in wrap(d, par, f, px(TRIM) - 2 * px(0.75)):
            w = d.textbbox((0, 0), line, font=f)[2]
            d.text((x_back + (px(TRIM) - w) // 2, y), line, font=f, fill=ink); y += 72
        y += 40
    # page thumbnails (sample)
    thumb = px(1.55)
    thumb_sources = approved()[:4]
    gap = px(0.25)
    total = len(thumb_sources) * thumb + (len(thumb_sources) - 1) * gap
    mx = x_back + (px(TRIM) - total) // 2
    my = y + px(0.2)
    for s in thumb_sources:
        m = Image.open(s).convert("RGB").resize((thumb, thumb), Image.LANCZOS)
        d.rectangle([mx - 6, my - 6, mx + thumb + 6, my + thumb + 6], fill=(255, 255, 255))
        cover.paste(m, (mx, my)); mx += thumb + gap
    # barcode area: white, 2 x 1.2 in, 0.25 in from the spine and the bottom trim
    bx1 = x_spine0 - px(0.25); bx0 = bx1 - px(2.0)
    by1 = px(BLEED + TRIM) - px(0.25); by0 = by1 - px(1.2)
    d.rectangle([bx0, by0, bx1, by1], fill=(255, 255, 255))
    # --- spine ---
    d.rectangle([x_spine0, 0, x_spine1, H], fill=tuple(book["spine_color"]))
    if n >= 80:  # KDP: 79+ (Cover Creator 80); we use 80 to stay safe
        clearance = px(0.0625)
        height = (x_spine1 - x_spine0) - 2 * clearance
        fs = font(F_TITLE, max(10, int(height * 0.8)))
        txt = book["title"].upper()
        tw, th = d.textbbox((0, 0), txt, font=fs)[2:]
        strip = Image.new("RGBA", (tw, th + 4), (0, 0, 0, 0))
        ImageDraw.Draw(strip).text((0, 0), txt, font=fs, fill=tuple(book["spine_text_color"]))
        strip = strip.rotate(-90, expand=True)
        cover.paste(strip, (x_spine0 + ((x_spine1 - x_spine0) - strip.width) // 2, (H - strip.height) // 2), strip)
    dest = os.path.join(kit, "cover.pdf")
    cover.save(dest, resolution=DPI)
    cover.save(os.path.join(kit, "cover-preview.png"))
    print(json.dumps({"cover": dest, "pages_used": n, "spine_in": round(spine, 4),
                      "width_in": round(W / DPI, 4), "height_in": round(H / DPI, 4),
                      "spine_text": n >= 80, "px": [W, H]}))
