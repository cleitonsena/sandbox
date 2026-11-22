#!/usr/bin/env python3
"""Provas 4: capa a sangrar (arte ate a borda), titulo branco com contorno escuro.
Uso: provas_capa4.py PASTA_FONTES SAIDA.png ARTE1 COR1 ARTE2 COR2 ARTE3 COR3 (COR = hex do contorno)"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

FT, SAIDA = sys.argv[1], sys.argv[2]
PARES = [(sys.argv[i], sys.argv[i + 1]) for i in range(3, len(sys.argv), 2)]
PPP = 300
px = lambda p: int(round(p * PPP))
W, H = px(8.625), px(8.75)
UTIL = W - px(0.125) - 2 * px(0.25) - px(0.3)
ANG = [-7, 5, -4, 6, -5, 4, -3, 6, -6, 4, -5, 6, -4, 5]
DY = [0.04, -0.05, 0.03, -0.04, 0.05, -0.04, 0.02, -0.05, 0.04, -0.02, 0.05, -0.04, 0.03, -0.05]
TIT = lambda t: ImageFont.truetype(os.path.join(FT, "cherrybombone/CherryBombOne-Regular.ttf"), max(8, int(t)))
SUB = ImageFont.truetype(os.path.join(FT, "fredoka/Fredoka[wdth,wght].ttf"), 70)
SUB.set_variation_by_axes([600, 100])


def hexc(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def letras(img, texto, alvo, y, cont, forte=1.0, track=-0.05):
    d = ImageDraw.Draw(img)
    tam = 900
    while True:
        avs = [d.textlength(c, font=TIT(tam)) for c in texto]
        tot = sum(avs) + track * tam * (len(texto) - 1) + 0.16 * tam * texto.count(" ")
        alt = TIT(tam).getbbox(texto.replace(" ", ""))
        if (alt[3] - alt[1]) <= alvo and tot <= UTIL:
            break
        tam -= 8
    f = TIT(tam); asc = f.getmetrics()[0]; s = int(tam * 0.07)
    x = (W - px(0.125) - tot) / 2
    for i, c in enumerate(texto):
        if c != " ":
            pad = int(tam * 0.5)
            lay = Image.new("RGBA", (int(avs[i]) + 2 * pad, int(tam * 1.4) + 2 * pad), (0, 0, 0, 0))
            dl = ImageDraw.Draw(lay)
            dl.text((pad, pad + asc + int(tam * 0.07)), c, font=f, fill=cont, anchor="ls", stroke_width=s, stroke_fill=cont)
            dl.text((pad, pad + asc), c, font=f, fill=(255, 255, 255), anchor="ls", stroke_width=s, stroke_fill=cont)
            lay = lay.rotate(ANG[i % len(ANG)] * forte, resample=Image.BICUBIC)
            img.paste(lay, (int(x) - pad, y - pad - alt[1] + int(DY[i % len(DY)] * forte * (alt[3] - alt[1]))), lay)
        x += avs[i] + track * tam + (0.16 * tam if c == " " else 0)
    return y + (alt[3] - alt[1]) + int(0.12 * (alt[3] - alt[1]))


def faixa(img, y, txt, cont):
    d = ImageDraw.Draw(img)
    w = d.textlength(txt, font=SUB)
    x = (W - px(0.125) - w) / 2
    d.rounded_rectangle([x - 40, y - 14, x + w + 40, y + 86], radius=50, fill=(255, 255, 255))
    d.text((x, y), txt, font=SUB, fill=cont)


capas = []
for arte, cor in PARES:
    cont = hexc(cor)
    im = Image.open(arte).convert("RGB").resize((W, W)).crop((0, 0, W, H)) if False else Image.open(arte).convert("RGB").resize((H, H), Image.LANCZOS).crop(((H - W) // 2, 0, (H - W) // 2 + W, H))
    y = letras(im, "COZY", px(1.3), px(0.125) + px(0.35), cont)
    y = letras(im, "LITTLE CORNERS", px(0.6), y + px(0.02), cont, forte=0.6)
    faixa(im, y + px(0.1), "50 BOLD & EASY DESIGNS FOR ADULTS", cont)
    capas.append(im)
th = 700; tw = int(W * th / H); mini = 260; mw = int(W * mini / H)
fol = Image.new("RGB", (len(capas) * (tw + 30) + 30, th + mini + 110), (255, 255, 255))
d = ImageDraw.Draw(fol)
lab = ImageFont.truetype(os.path.join(FT, "nunito/Nunito[wght].ttf"), 30)
for i, im in enumerate(capas):
    x = 30 + i * (tw + 30)
    d.text((x, 10), f"Prova {'ABC'[i]}", font=lab, fill=(0, 0, 0))
    fol.paste(im.resize((tw, th), Image.LANCZOS), (x, 50))
    d.text((x, th + 60), "tamanho na pesquisa:", font=lab, fill=(120, 120, 120))
    fol.paste(im.resize((mw, mini), Image.LANCZOS), (x, th + 100))
fol.save(SAIDA)
print("ok", fol.size)
