#!/usr/bin/env python3
"""Provas 3: titulo mais perto da referencia 'Snuggle'.
Diferencas aplicadas: letras coladas (tracking negativo), rotacao maior, cada letra com tamanho
e altura diferentes, cor mostarda com contorno, estrelinhas de 4 pontas. So fontes OFL 1.1.
Uso: provas3.py PASTA_FONTES ARTE.png SAIDA.png"""
import math, os, sys
from PIL import Image, ImageDraw, ImageFont

FT, ARTE, SAIDA = sys.argv[1], sys.argv[2], sys.argv[3]
PPP = 300
px = lambda p: int(round(p * PPP))
FUNDO, CAST, TERRA, MOST = (253, 240, 219), (92, 58, 40), (196, 120, 86), (240, 190, 80)
W, H = px(8.625), px(8.75)
UTIL = W - px(0.125) - 2 * px(0.25) - px(0.3)
arte = Image.open(ARTE).convert("RGB")

ANG = [-10, 7, -5, 9, -8, 6, -4, 8, -9, 5, -7, 9, -6, 7]
DY = [0.06, -0.08, 0.04, -0.05, 0.08, -0.06, 0.03, -0.08, 0.06, -0.03, 0.07, -0.06, 0.04, -0.07]
SC = [1.12, 0.94, 1.04, 0.96, 1.08, 0.95, 1.03, 0.97, 1.1, 0.94, 1.05, 0.98, 1.07, 0.95]


def F(path, tam, eixos=None):
    f = ImageFont.truetype(os.path.join(FT, path), max(8, int(tam)))
    if eixos:
        f.set_variation_by_axes(eixos)
    return f


def letras(img, texto, mk, alvo, y, cor, contorno=None, sombra=None, track=-0.09, forte=1.0):
    """Cada letra: tamanho, angulo e altura proprios; letras quase a tocar. y = topo; devolve fundo."""
    d = ImageDraw.Draw(img)
    tam = 900
    while True:
        fs = [mk(tam * (SC[i % len(SC)] if c != " " else 1)) for i, c in enumerate(texto)]
        avs = [d.textlength(c, font=f) for c, f in zip(texto, fs)]
        esp = [0.12 * tam if c == " " else 0 for c in texto]
        tot = sum(avs) + track * tam * (len(texto) - 1) + sum(esp)
        alt = mk(tam).getbbox(texto.replace(" ", ""))
        if (alt[3] - alt[1]) <= alvo and tot <= UTIL:
            break
        tam -= 8
    asc = mk(tam).getmetrics()[0]
    topo_ref = alt[1]
    x = (W - px(0.125) - tot) / 2
    s = int(tam * 0.045) if contorno else 0
    for i, (c, f) in enumerate(zip(texto, fs)):
        if c != " ":
            pad = int(tam * 0.5)
            lay = Image.new("RGBA", (int(avs[i]) + 2 * pad, int(tam * 1.4) + 2 * pad), (0, 0, 0, 0))
            dl = ImageDraw.Draw(lay)
            base = pad + asc
            if sombra:
                dl.text((pad + sombra[0], base + sombra[1]), c, font=f, fill=sombra[2], anchor="ls",
                        stroke_width=s, stroke_fill=sombra[2])
            dl.text((pad, base), c, font=f, fill=cor, anchor="ls", stroke_width=s, stroke_fill=contorno)
            lay = lay.rotate(ANG[i % len(ANG)] * forte, resample=Image.BICUBIC, expand=False)
            dy = int(DY[i % len(DY)] * forte * (alt[3] - alt[1]))
            img.paste(lay, (int(x) - pad, y - pad - topo_ref + dy), lay)
        x += avs[i] + track * tam + esp[i]
    return y + (alt[3] - alt[1]) + int(0.1 * (alt[3] - alt[1]))


def estrela(d, cx, cy, r, cor):
    pts = []
    for k in range(8):
        a = math.pi / 4 * k - math.pi / 2
        rr = r if k % 2 == 0 else r * 0.32
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=cor)


def subtitulo(img, y, cor):
    d = ImageDraw.Draw(img)
    f = F("fredoka/Fredoka[wdth,wght].ttf", 84, [600, 100])
    for ln in ["50 BOLD & EASY DESIGNS", "FOR ADULTS"]:
        w = sum(d.textlength(c, font=f) for c in ln) + 0.05 * 84 * (len(ln) - 1)
        x = (W - px(0.125) - w) / 2
        for c in ln:
            d.text((x, y), c, font=f, fill=cor); x += d.textlength(c, font=f) + 0.05 * 84
        y += 96


def base():
    im = Image.new("RGB", (W, H), FUNDO)
    lado = px(5.2)
    im.paste(arte.resize((lado, lado), Image.LANCZOS), ((W - px(0.125) - lado) // 2, H - px(0.2) - lado))
    return im


FONTES = [
    ("DynaPuff", lambda t: F("dynapuff/DynaPuff[wdth,wght].ttf", t, [700, 100])),
    ("Bagel Fat One", lambda t: F("bagelfatone/BagelFatOne-Regular.ttf", t)),
    ("Cherry Bomb One", lambda t: F("cherrybombone/CherryBombOne-Regular.ttf", t)),
    ("Sour Gummy", lambda t: F("sourgummy/SourGummy[wdth,wght].ttf", t, [125, 900])),
]
CORES = [
    ("castanho", dict(cor=CAST, contorno=None, sombra=None), MOST),
    ("mostarda + contorno", dict(cor=MOST, contorno=CAST, sombra=(0, 22, CAST)), TERRA),
]

th = 760; tw = int(W * th / H)
lab = F("nunito/Nunito[wght].ttf", 30, [800])
fol = Image.new("RGB", (4 * tw + 100, 2 * (th + 50) + 30), (235, 235, 235))
dd = ImageDraw.Draw(fol)
n = 0
for j, (cnome, cfg, cestrela) in enumerate(CORES):
    for i, (fnome, mk) in enumerate(FONTES):
        n += 1
        im = base()
        y = letras(im, "COZY", mk, px(1.25), px(0.125) + px(0.45), **cfg)
        y = letras(im, "LITTLE CORNERS", mk, px(0.55), y + px(0.05), forte=0.6, **cfg)
        subtitulo(im, y + px(0.12), TERRA if j == 0 else CAST)
        d = ImageDraw.Draw(im)
        for (ex, ey, r) in [(0.13, 0.07, 70), (0.86, 0.1, 55), (0.9, 0.2, 35), (0.1, 0.19, 40)]:
            estrela(d, ex * (W - px(0.125)), ey * H, r, cestrela)
        x, yy = 20 + i * (tw + 20), 20 + j * (th + 50)
        dd.text((x, yy), f"{n} {fnome}, {cnome}", font=lab, fill=(40, 40, 40))
        fol.paste(im.resize((tw, th), Image.LANCZOS), (x, yy + 40))
fol.save(SAIDA)
print("ok", fol.size)
