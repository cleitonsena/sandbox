#!/usr/bin/env python3
"""effects (26 Nov 2026): bending text in code, to use with typography.py.
  circle(): letters following a circular arc (like a seal).
  bend(): curves the whole mask: 'bridge' (arc up), 'smile' (down), 'bulge' (swells in the middle), 'wave'.
  emboss(): light letter with an offset dark shadow, a thick-print look.
Run directly to build the sample: effects.py OUTPUT"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from typography import STYLES, DR, YS, FR, block, ink, paper, apply, font, noise


def circle(text, s, cap, radius, center_deg=-90, direction=1, track=0.15, full=False):
    """letters around a circle. center_deg: where the middle of the text sits (-90 = top). direction 1 = reads outside."""
    t = max(6, int(100 * cap / (font(s, 100).getbbox("H")[3] - font(s, 100).getbbox("H")[1])))
    f = font(s, t); top = f.getbbox("H")[1]
    if full:  # spreads the letters over the whole turn
        track = (2 * np.pi * (radius + (cap / 2 if direction == 1 else -cap / 2)) - sum(f.getlength(c) for c in text)) / len(text) / t
    widths = [f.getlength(c) + track * t for c in text]; total = sum(widths) - track * t
    radius_txt = radius; radius = radius + (cap / 2 if direction == 1 else -cap / 2)  # angles measured at the middle of the letter
    L = int(2 * (radius_txt + cap * 2)); a = Image.new("L", (L, L), 0); cx = cy = L / 2
    ang = np.radians(center_deg) - direction * total / 2 / radius
    for c, w in zip(text, widths):
        mid = ang + direction * (w - track * t) / 2 / radius
        p = int(cap * 0.6); im = Image.new("L", (int(f.getlength(c)) + 2 * p + 1, cap + 2 * p), 0)
        ImageDraw.Draw(im).text((p, p - top), c, font=f, fill=255)
        im = im.rotate(-np.degrees(mid) - 90 * direction, Image.BICUBIC, expand=True)
        r = radius
        x, y = cx + r * np.cos(mid), cy + r * np.sin(mid)
        a.paste(im, (int(x - im.width / 2), int(y - im.height / 2)), im)
        ang += direction * w / radius
    arr = np.asarray(a, np.float32); ys, xs = np.nonzero(arr > 8)
    return arr[ys.min() - 4:ys.max() + 4, xs.min() - 4:xs.max() + 4], cap


def bend(a, mode, strength=0.25):
    """strength = maximum shift as a fraction of the block height"""
    h, w = a.shape; x = np.linspace(-1, 1, w); d = strength * h
    if mode in ("bridge", "smile"):
        shift = d * (1 - x ** 2) * (1 if mode == "smile" else -1)
        pad = int(abs(d)) + 2; b = np.zeros((h + 2 * pad, w), np.float32)
        for i in range(w): b[pad + int(shift[i]):pad + int(shift[i]) + h, i] = a[:, i]
        return b
    if mode == "bulge":  # each column stretches vertically, more in the middle
        sc = 1 + strength * (1 - x ** 2); H = int(h * (1 + strength)) + 2; b = np.zeros((H, w), np.float32)
        for i in range(w):
            hh = max(1, int(h * sc[i])); col = np.interp(np.linspace(0, h - 1, hh), np.arange(h), a[:, i])
            o = (H - hh) // 2; b[o:o + hh, i] = col
        return b
    if mode == "wave":
        shift = (d * np.sin(x * np.pi * 1.5)).astype(int); pad = int(abs(d)) + 2
        b = np.zeros((h + 2 * pad, w), np.float32)
        for i in range(w): b[pad + shift[i]:pad + shift[i] + h, i] = a[:, i]
        return b
    return a


def emboss(bg, alpha, x, y, color, shadow, offset, seed=1):
    """offset dark shadow first, then the light letter on top"""
    apply(bg, np.asarray(Image.fromarray((alpha[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(offset / 8)),
                         np.float32)[..., None] / 255 * 0.85, x + offset, y + offset, shadow, seed)
    apply(bg, alpha, x, y, color, seed + 1)


if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True); W, H = 1000, 1000
    P, S = STYLES["black"], STYLES["seventies"]; cards = []

    # 1. circular seal (Black H3) around a title
    f = paper("black", W, H, 1)
    a, c = circle("LISTEN CLOSELY * LISTEN CLOSELY * LISTEN CLOSELY * ", P["h3"]["della-spaced"], 34, 360, -90, 1, full=True)
    apply(f, ink(a, c, False), (W - a.shape[1]) // 2, (H - a.shape[0]) // 2, P["color"]["h3"])
    a, c = block(["QUIET", "MIND"], P["h1"]["della-bold"], width=440, align="center")
    apply(f, ink(a, c, False), (W - a.shape[1]) // 2, (H - a.shape[0]) // 2, P["color"]["h1"])
    cards.append(("1. circle (seal)", f))

    # 2. arc on top only, short text
    f = paper("black", W, H, 2)
    a, c = circle("NOTES TO SELF", P["h3"]["della-spaced"], 40, 330, -90, 1, 0.3)
    apply(f, ink(a, c, False), (W - a.shape[1]) // 2, 120, P["color"]["h3"])
    a, c = block(["SEE WHAT", "IS ALREADY", "HERE"], P["h1"]["della-bold"], width=760)
    apply(f, ink(a, c, False), 120, 520, P["color"]["h1"])
    cards.append(("2. arc on top", f))

    # 3-5. Seventies H1 bent
    for i, (mode, strength) in enumerate([("bridge", 0.22), ("bulge", 0.30), ("wave", 0.12)]):
        f = paper("cream", W, H, 3 + i)
        a, c = block(["ROOM", "TO GROW"], S["h1"]["fraunces-black"], width=820, align="center", seed=3 + i)
        a = bend(a, mode, strength)
        apply(f, ink(a, c, True, 3 + i), (W - a.shape[1]) // 2, (H - a.shape[0]) // 2, S["color"]["h1"])
        cards.append((f"{3 + i}. {mode}", f))

    # 6. thick lowercase with emboss, purple background (our color)
    f = paper("black", W, H, 9); f = f * 0 + np.array([92, 38, 112], np.float32) + (f - 24) * 0.8
    s6 = dict(font=YS, hx=4, track=-0.02, leading=0.98)
    a, c = block(["slow is", "still", "moving."], s6, width=760, align="left")
    a = bend(a, "bridge", 0.06)
    emboss(f, ink(a, c, False), 120, (H - a.shape[0]) // 2, (222, 214, 226), (40, 14, 52), 9)
    cards.append(("6. lowercase with emboss", f))

    w = 400; sheet = Image.new("RGB", (w * 3 + 20, (w + 30) * 2), "white"); d = ImageDraw.Draw(sheet)
    for i, (name, arr) in enumerate(cards):
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)); im.save(f"{out}/{i + 1}.png")
        x, y = (i % 3) * (w + 10), (i // 3) * (w + 30)
        sheet.paste(im.resize((w, w)), (x, y + 30)); d.text((x + 4, y + 10), name, fill="black")
        print(name, "ok", flush=True)
    sheet.save(f"{out}/sheet.jpg", quality=88)
