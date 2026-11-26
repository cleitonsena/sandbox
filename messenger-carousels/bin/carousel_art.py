#!/usr/bin/env python3
"""carousel_art (26 Nov 2026): the carousel visual recipe as functions, for carousel_auto.py.
Same style: BLACK line, figures with an aura, Young Serif title with one bigger line, label "A MESSAGE FOR YOU n/4",
handle right below the title, dark veil behind the title, 4th CTA slide with our own icons."""
import numpy as np
from PIL import Image, ImageDraw
from typography import STYLES, block, ink, apply, paper

W, H = 1080, 1350; P = STYLES["black"]; HANDLE = "@YOURBESTIETHEMESSENGER"; FONT_H1 = P["h1"]["young"]
CREAM, AURA = P["color"]["h1"], (246, 158, 72)
CAP = 58
STYLE = ("Portrait illustration, dark risograph print on near-black paper with heavy grain, dust and slight misregistration. "
         "{scene} Every figure is a dark silhouette with a glowing thermal aura that follows its outline in bands of yellow, "
         "orange, hot magenta and violet, visible hand-drawn pastel strokes, 1970s psychedelic poster mood. "
         "The {empty} third of the image is empty dark paper with only faint grain. "
         "No text, no letters, no numbers, no clock digits, no logo, no signature, no watermark.")


def text_block(lines, cap, width):
    parts = [block([l], FONT_H1, cap=cap * k, width=width, align="center", seed=i + 1)[0] for i, (l, k) in enumerate(lines)]
    w = max(a.shape[1] for a in parts); gap = int(cap * 0.12)
    m = np.zeros((sum(a.shape[0] for a in parts) + gap * (len(parts) - 1), w), np.float32); y = 0
    for a in parts:
        x = (w - a.shape[1]) // 2; m[y:y + a.shape[0], x:x + a.shape[1]] = np.maximum(m[y:y + a.shape[0], x:x + a.shape[1]], a)
        y += a.shape[0] + gap
    return m


def veil(f, y0, y1, strength=0.6, edge=140):
    ys = np.arange(H, dtype=np.float32); k = np.clip(np.minimum(ys - (y0 - edge), (y1 + edge) - ys) / edge, 0, 1)
    f *= (1 - strength * k ** 1.5)[:, None, None]


def slide(bg, output, n, total, lines, pos):
    im = Image.open(bg).convert("RGB"); sz = im.width * 5 / 4
    top = int((im.height - sz) * (1.0 if pos == "top" else 0.0))
    im = im.crop((0, top, im.width, top + int(sz))).resize((W, H), Image.LANCZOS)
    f = np.asarray(im, np.float32).copy()
    a3, c3 = block([f"A MESSAGE FOR YOU  {n}/{total}"], P["h3"]["della-spaced"], cap=16, align="center")
    apply(f, ink(a3, c3, False), (W - a3.shape[1]) // 2, 70, P["color"]["h3"], 3)
    m = text_block(lines, CAP, W - 180); a4, c4 = block([HANDLE], P["h3"]["della-spaced"], cap=12, align="center")
    tall = m.shape[0] + 34 + a4.shape[0]; y = 130 if pos == "top" else H - 90 - tall
    veil(f, y - 40, y + tall + 40)
    apply(f, ink(m, CAP, False, n), (W - m.shape[1]) // 2, y, CREAM, 5)
    apply(f, ink(a4, c4, False), (W - a4.shape[1]) // 2, y + m.shape[0] + 34, P["color"]["h3"], 4)
    Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).save(output)


def icon(kind, t):
    S = 4 * t; im = Image.new("L", (S, S), 0); d = ImageDraw.Draw(im); lw = max(3, S // 11); c = S / 2; r = S * 0.4
    if kind == "like":
        tt = np.linspace(0, 2 * np.pi, 200); x = 16 * np.sin(tt) ** 3; y = -(13 * np.cos(tt) - 5 * np.cos(2 * tt) - 2 * np.cos(3 * tt) - np.cos(4 * tt))
        pts = list(zip(c + x / 17 * r, c + y / 17 * r + S * 0.03)); d.line(pts + [pts[0]], fill=255, width=lw, joint="curve")
    elif kind == "comment":
        d.ellipse((c - r, c - r, c + r, c + r), outline=255, width=lw)
        d.polygon([(c - r * 0.72, c + r * 0.55), (c - r * 0.95, c + r * 1.02), (c - r * 0.35, c + r * 0.88)], fill=255)
    elif kind == "share":
        a, b, e = (c - r, c - r * 0.45), (c + r, c - r * 0.95), (c + r * 0.05, c + r)
        d.line([a, b, e, a], fill=255, width=lw, joint="curve"); d.line([b, (c - r * 0.25, c - r * 0.1)], fill=255, width=lw)
    else:
        x0, x1, y0, y1 = c - r * 0.62, c + r * 0.62, c - r, c + r
        d.line([(x0, y1), (x0, y0), (x1, y0), (x1, y1), (c, y1 - r * 0.55), (x0, y1)], fill=255, width=lw, joint="curve")
    return np.asarray(im.resize((t, t), Image.LANCZOS), np.float32)


def slide_cta(output, word):
    f = paper("black", W, H, 11)
    a3, c3 = block(["A MESSAGE FOR YOU  4/4"], P["h3"]["della-spaced"], cap=16, align="center")
    apply(f, ink(a3, c3, False), (W - a3.shape[1]) // 2, 70, P["color"]["h3"], 3)
    m = text_block([("if this found you,", 1), ("pass it on.", 1.35)], CAP, W - 180)
    apply(f, ink(m, CAP, False, 7), (W - m.shape[1]) // 2, 150, CREAM, 5)
    lines = [("like", "like it if you needed this"), ("comment", f"comment “{word}” below"),
             ("share", "share it with your bestie"), ("save", "save it for the hard days")]
    t, step, x0 = 104, 104 + 78, 130
    y = 150 + m.shape[0] + ((H - 150 - m.shape[0] - 120) - (4 * step - 78)) // 2
    for i, (k, phrase) in enumerate(lines):
        ic = icon(k, t); apply(f, ink(ic, t, False, 20 + i), x0, y, AURA, 30 + i)
        a, ca = block([phrase], FONT_H1, cap=44, width=W - x0 - t - 50 - 60, seed=40 + i)
        apply(f, ink(a, ca, False, 50 + i), x0 + t + 50, y + (t - a.shape[0]) // 2, CREAM, 60 + i); y += step
    a4, c4 = block([HANDLE], P["h3"]["della-spaced"], cap=12, align="center")
    apply(f, ink(a4, c4, False), (W - a4.shape[1]) // 2, H - 90, P["color"]["h3"], 4)
    Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).save(output)


def contact_sheet(folder, keys):
    w = 300; hh = int(w * 1.25); sh = Image.new("RGB", (w * 4 + 30, (hh + 30) * len(keys)), "white"); d = ImageDraw.Draw(sh)
    for i, c in enumerate(keys):
        for j in range(4):
            x, y = j * (w + 10), i * (hh + 30); sh.paste(Image.open(f"{folder}/{c}-{j + 1}.png").resize((w, hh)), (x, y + 30))
            d.text((x + 4, y + 10), f"{c} {j + 1}/4", fill="black")
    sh.save(f"{folder}/sheet.jpg", quality=88)
