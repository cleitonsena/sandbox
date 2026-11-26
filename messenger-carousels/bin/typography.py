#!/usr/bin/env python3
"""typography (26 Nov 2026): lettering design system for the posters. Two visual lines:
  BLACK     = engraving on black, greyish-white letters, no bounce (recipe type3).
  SEVENTIES = brick red on cream, bouncing letters, worn ink (recipe type4).
Each line has roles H1 (title), H2 (subtitle) and H3 (small spaced label).
Use: from typography import STYLES, block, ink, paper, apply.
Run directly to build the sample sheet: typography.py OUTPUT"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
F = lambda n: os.path.expanduser(f"~/books/fonts/{n}")
DR = F("dellarespira/DellaRespira-Regular.ttf")
YS = F("youngserif/YoungSerif-Regular.ttf")
FR = F("fraunces/Fraunces[SOFT,WONK,opsz,wght].ttf")  # axes: opsz, wght, SOFT, WONK

# hx/hy/wave in px for a letter 150 px tall; they scale with the size
STYLES = {
    "black": {
        "paper": "black", "color": {"h1": (215, 212, 205), "h2": (215, 212, 205), "h3": (200, 197, 190)}, "worn": False,
        "h1": {"della-bold": dict(font=DR, hx=3, track=-0.015, comp=0.94, leading=1.12),
               "young": dict(font=YS, hx=1, track=-0.01, comp=0.96, leading=1.10)},
        "h2": {"della-thin": dict(font=DR, hx=1, track=0.0, leading=1.15)},
        "h3": {"della-spaced": dict(font=DR, hx=1, track=0.35, leading=1.2)},
    },
    "seventies": {
        "paper": "cream", "color": {"h1": (168, 52, 36), "h2": (168, 52, 36), "h3": (45, 32, 28)}, "worn": True,
        "h1": {"fraunces-black": dict(font=FR, axes=[144, 900, 100, 1], track=-0.02, jump=0.05, spin=3, wave=6, leading=1.20),
               "young": dict(font=YS, hx=3, track=-0.01, jump=0.05, spin=3, wave=6, leading=1.20),
               "della-bold": dict(font=DR, hx=5, track=0.01, jump=0.05, spin=3, wave=6, leading=1.20)},
        "h2": {"fraunces-semi": dict(font=FR, axes=[144, 650, 100, 1], hx=2, track=-0.01, leading=1.15),
               "young-calm": dict(font=YS, hx=3, track=-0.01, leading=1.15)},
        "h3": {"della-spaced": dict(font=DR, hx=2, track=0.35, leading=1.2)},
    },
}
# size of the roles relative to the H1 letter height
RATIO = {"h2": 0.30, "h3": 0.15}


def noise(w, h, cell, seed):
    p = np.random.default_rng(seed).uniform(0, 1, (max(2, h // cell), max(2, w // cell))).astype(np.float32)
    return np.asarray(Image.fromarray((p * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255


def font(s, t):
    f = ImageFont.truetype(s["font"], t)
    if s.get("axes"): f.set_variation_by_axes(s["axes"])
    return f


def _cap(s, t):
    b = font(s, t).getbbox("H"); return b[3] - b[1]


def _width(lines, s, t):
    f = font(s, t); tr = s.get("track", 0) * t
    return max(sum(f.getlength(c) for c in l) + tr * (len(l) - 1) for l in lines)


def block(lines, s, cap=None, width=None, align="left", seed=1):
    """0..255 mask of the text. Pass cap (letter height in px) or width (width to fill). Returns (mask, cap)."""
    comp, tr = s.get("comp", 1.0), s.get("track", 0.0)
    if cap:
        t = max(6, int(100 * cap / _cap(s, 100)))
        while width and _width(lines, s, t) * comp > width and t > 6: t -= 1  # never wider than width
    else:
        t = 500
        while _width(lines, s, t) * comp + 2 * s.get("hx", 0) * _cap(s, t) / 150 > width and t > 8: t -= 2
    f = font(s, t); top = f.getbbox("H")[1]; c = _cap(s, t); k = c / 150
    hx, hy, wave = round(s.get("hx", 0) * k), round(s.get("hy", 0) * k), s.get("wave", 0) * k
    rn = np.random.default_rng(seed); jump, spin = s.get("jump", 0), s.get("spin", 0)
    pad = int(c * 0.6); step = int(c * s.get("leading", 1.12)); lmax = _width(lines, s, t)
    Wd, Hd = int(lmax) + 2 * pad, step * (len(lines) - 1) + c + 2 * pad
    a = np.zeros((Hd, Wd), np.float32); y = pad
    for l in lines:
        lw = sum(f.getlength(ch) for ch in l) + tr * t * (len(l) - 1)
        x = pad + ((lmax - lw) / 2 if align == "center" else 0)
        for ch in l:
            p = int(c * 0.5); im = Image.new("L", (int(f.getlength(ch)) + 2 * p + 1, c + 2 * p), 0)
            ImageDraw.Draw(im).text((p, p - top), ch, font=f, fill=255)
            if spin: im = im.rotate(rn.uniform(-spin, spin), Image.BICUBIC)
            dy = int(rn.uniform(-jump, jump) * c) if jump else 0
            x0, y0 = int(x) - p, y - p + dy; ar = np.asarray(im, np.float32)
            ys, xs = max(0, -y0), max(0, -x0); ye, xe = min(ar.shape[0], Hd - y0), min(ar.shape[1], Wd - x0)
            if ye > ys and xe > xs:
                reg = a[y0 + ys:y0 + ye, x0 + xs:x0 + xe]; np.maximum(reg, ar[ys:ye, xs:xe], out=reg)
            x += f.getlength(ch) + tr * t
        y += step
    for sh in range(1, hx + 1): a = np.maximum(a, np.maximum(np.roll(a, sh, 1), np.roll(a, -sh, 1)))
    for sh in range(1, hy + 1): a = np.maximum(a, np.maximum(np.roll(a, sh, 0), np.roll(a, -sh, 0)))
    if wave:
        shift = (wave * np.sin(np.arange(Wd) / max(Wd, 1) * 2 * np.pi * 1.3 + seed)).astype(int)
        a = np.stack([np.roll(a[:, i], shift[i]) for i in range(Wd)], 1)
    if comp != 1.0:
        a = np.asarray(Image.fromarray(a.astype(np.uint8)).resize((max(1, int(Wd * comp)), Hd), Image.LANCZOS), np.float32)
    ys, xs = np.nonzero(a > 8)
    m = max(2, int(c * 0.08))
    a = a[max(0, ys.min() - m):ys.max() + m, max(0, xs.min() - m):xs.max() + m]
    return a, c


def ink(a, cap, worn, seed=1):
    """irregular ink edge; with worn=True, worn screen-print ink. Returns alpha 0..1 (H, W, 1)."""
    h, w = a.shape; k = cap / 150
    b = np.asarray(Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(0.5, 2.0 * k))), np.float32) / 255
    b = np.clip((b + (noise(w, h, max(2, round(3 * k)), seed) - 0.5) * 0.35 - 0.5) * 5 + 0.5, 0, 1)
    if worn:
        fl = noise(w, h, max(2, round(9 * k)), seed + 1) * 0.6 + noise(w, h, max(2, round(40 * k)), seed + 2) * 0.4
        b = b * np.clip(1.25 - fl * 0.55, 0.55, 1)
    b = np.asarray(Image.fromarray((b * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(0.4, 0.7 * k))), np.float32)
    return b[..., None] / 255


def paper(kind, W, H, seed=1):
    rn = np.random.default_rng(seed)
    if kind == "black":
        v = 24 + (noise(W, H, 60, seed) - 0.5) * 14 + rn.normal(0, 10, (H, W))
        return np.repeat(v[..., None], 3, 2).astype(np.float32)
    v = np.array([228, 214, 188], np.float32) + ((noise(W, H, 80, seed) - 0.5) * 26)[..., None]
    v -= (noise(W, H, 25, seed + 1) > 0.82)[..., None] * np.array([10, 14, 20], np.float32)
    return v + rn.normal(0, 9, (H, W, 1))


def apply(bg, alpha, x, y, color, seed=1):
    """paints alpha over the background (float HxWx3 array) at x,y, with grain in the color"""
    h, w = alpha.shape[:2]; H, W = bg.shape[:2]
    h, w = min(h, H - y), min(w, W - x); alpha = alpha[:h, :w]
    color = np.array(color, np.float32) + ((noise(w, h, 30, seed) - 0.5) * 24)[..., None] + np.random.default_rng(seed).normal(0, 10, (h, w, 1))
    bg[y:y + h, x:x + w] = bg[y:y + h, x:x + w] * (1 - alpha) + color * alpha


def poster(line, h1, h2, texts, W=1000, H=1400, seed=1):
    """hierarchy sample: H3 + H1 + H2 and the illustration area marked"""
    E = STYLES[line]; m = 80; bg = paper(E["paper"], W, H, seed)
    a1, cap1 = block(texts["h1"], E["h1"][h1], width=W - 2 * m, align="left" if line == "black" else "center", seed=seed)
    al = "left" if line == "black" else "center"
    a2, cap2 = block(texts["h2"], E["h2"][h2], cap=cap1 * RATIO["h2"], width=W - 2 * m, align=al, seed=seed + 1)
    a3, cap3 = block(texts["h3"], list(E["h3"].values())[0], cap=cap1 * RATIO["h3"], width=W - 2 * m, align=al, seed=seed + 2)
    pos = lambda a: m if al == "left" else (W - a.shape[1]) // 2
    if line == "black":  # illustration on top, text below
        y3 = H - m - a2.shape[0] - a1.shape[0] - a3.shape[0] - 70; area = (m, m, W - m, y3 - 40)
    else:  # text on top, illustration below
        y3 = m; area = (m, m + a3.shape[0] + a1.shape[0] + a2.shape[0] + 110, W - m, H - m)
    y1 = y3 + a3.shape[0] + 30; y2 = y1 + a1.shape[0] + 40
    for a, c, y, role in [(a3, cap3, y3, "h3"), (a1, cap1, y1, "h1"), (a2, cap2, y2, "h2")]:
        apply(bg, ink(a, c, E["worn"], seed), pos(a), y, E["color"][role], seed)
    im = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im); tone = (90, 90, 90) if line == "black" else (170, 150, 125)
    d.rectangle(area, outline=tone, width=2); d.text((area[0] + 12, area[1] + 10), "illustration", fill=tone)
    return im


TEXTS = {
    "black": {"h3": ["NOTES TO SELF"], "h1": ["SEE WHAT", "IS ALREADY", "HERE"], "h2": ["ONE QUIET THOUGHT FOR EACH DAY"]},
    "seventies": {"h3": ["DAILY PRACTICE"], "h1": ["ROOM", "TO GROW"], "h2": ["SMALL STEPS FOR A KINDER MIND"]},
}
SAMPLES = [("black", "della-bold", "della-thin"), ("black", "young", "della-thin"),
           ("seventies", "fraunces-black", "fraunces-semi"), ("seventies", "young", "young-calm"),
           ("seventies", "della-bold", "fraunces-semi")]

if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True); w, h = 400, 560
    sheet = Image.new("RGB", (w * 5 + 40, h + 70), "white"); d = ImageDraw.Draw(sheet)
    for i, (line, h1, h2) in enumerate(SAMPLES):
        im = poster(line, h1, h2, TEXTS[line], seed=11 + i); name = f"{i + 1}-{line}-{h1}"
        im.save(f"{out}/{name}.png"); sheet.paste(im.resize((w, h)), (i * (w + 10), 70))
        d.text((i * (w + 10) + 4, 6), f"{i + 1}. {line.upper()}", fill="black")
        d.text((i * (w + 10) + 4, 24), f"H1 {h1}  H2 {h2}", fill="black")
        d.text((i * (w + 10) + 4, 42), f"H3 della spaced", fill="black")
        print(name, "ok", flush=True)
    sheet.save(f"{out}/sheet.jpg", quality=88)
