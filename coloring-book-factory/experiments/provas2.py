#!/usr/bin/env python3
"""Provas 2: titulo em letras redondas e saltitantes (referencia 'Snuggle') + subtitulo redondo em maiusculas.
Uso: provas2.py PASTA_FONTES ARTE.png SAIDA.png. So fontes OFL 1.1."""
import os, sys
from PIL import Image, ImageDraw, ImageFont

FT, ARTE, SAIDA = sys.argv[1], sys.argv[2], sys.argv[3]
PPP = 300
px = lambda p: int(round(p * PPP))
FUNDO, CAST, TERRA = (253, 240, 219), (92, 58, 40), (196, 120, 86)
W, H = px(8.625), px(8.75)
UTIL = W - px(0.125) - 2 * px(0.25) - px(0.3)  # largura maxima do titulo dentro da zona segura
arte = Image.open(ARTE).convert("RGB")


def F(path, tam, eixos=None):
    f = ImageFont.truetype(os.path.join(FT, path), tam)
    if eixos:
        f.set_variation_by_axes(eixos)
    return f


ANG = [-6, 4, -3, 6, -4, 3, -5, 5, -2, 4, -6, 3, -4, 5]
DY = [0.00, -0.05, 0.03, -0.03, 0.05, -0.02, 0.04, -0.05, 0.02, -0.04, 0.03, -0.01, 0.05, -0.03]


def saltitante(img, texto, mk, alvo, y, cor, track=-0.03, salto=True):
    """Letra a letra, rodada e deslocada (efeito desenhado a mao). Tamanho escolhido pela altura
    real da tinta (alvo, em px) e limitado pela largura util. y = topo da tinta. Devolve fundo da tinta."""
    tam = 800
    d = ImageDraw.Draw(img)
    while True:
        f = mk(tam)
        bb = f.getbbox(texto)
        avs = [d.textlength(c, font=f) for c in texto]
        tot = sum(avs) + track * tam * (len(texto) - 1) + 0.14 * tam * texto.count(' ')
        if (bb[3] - bb[1]) <= alvo and tot <= UTIL:
            break
        tam -= 6
    x = (W - px(0.125) - tot) / 2
    for i, c in enumerate(texto):
        if c != " ":
            pad = int(tam * 0.4)
            lay = Image.new("RGBA", (int(avs[i]) + 2 * pad, int(tam * 1.6) + 2 * pad), (0, 0, 0, 0))
            ImageDraw.Draw(lay).text((pad, pad - bb[1]), c, font=f, fill=cor)
            if salto:
                lay = lay.rotate(ANG[i % len(ANG)], resample=Image.BICUBIC, expand=False)
            dy = int(DY[i % len(DY)] * (bb[3] - bb[1])) if salto else 0
            img.paste(lay, (int(x) - pad, y - pad + dy), lay)
        x += avs[i] + track * tam + (0.14 * tam if c == ' ' else 0)
    return y + (bb[3] - bb[1]) + int(0.06 * (bb[3] - bb[1]))


def subtitulo(img, y, mk, tam, cor, track=0.06):
    d = ImageDraw.Draw(img)
    for ln in ["50 BOLD & EASY DESIGNS", "FOR ADULTS"]:
        f = mk(tam)
        avs = [d.textlength(c, font=f) for c in ln]
        tot = sum(avs) + track * tam * (len(ln) - 1)
        x = (W - px(0.125) - tot) / 2
        for c, a in zip(ln, avs):
            d.text((x, y), c, font=f, fill=cor); x += a + track * tam
        y += int(tam * 1.1)
    return y


def base():
    im = Image.new("RGB", (W, H), FUNDO)
    lado = px(5.3)
    im.paste(arte.resize((lado, lado), Image.LANCZOS), ((W - px(0.125) - lado) // 2, H - px(0.2) - lado))
    return im


SUB_FREDOKA = lambda t: F("fredoka/Fredoka[wdth,wght].ttf", t, [600, 100])
TITULOS = [
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
alt_sub = 300
fol = Image.new("RGB", (3 * tw + 80, 3 * (th + 50) + 70 + alt_sub + 50), (235, 235, 235))
dd = ImageDraw.Draw(fol)
for i, (nome, mk) in enumerate(TITULOS):
    im = base()
    y = saltitante(im, "COZY", mk, px(1.15), px(0.125) + px(0.4), CAST)
    y = saltitante(im, "LITTLE CORNERS", mk, px(0.5), y + px(0.1), CAST)
    subtitulo(im, y + px(0.14), SUB_FREDOKA, 70, TERRA)
    x, yy = 20 + (i % 3) * (tw + 20), 20 + (i // 3) * (th + 50)
    dd.text((x, yy), f"{i + 1} {nome}", font=lab, fill=(40, 40, 40))
    fol.paste(im.resize((tw, th), Image.LANCZOS), (x, yy + 40))
# faixa de subtitulos
y0 = 20 + 3 * (th + 50) + 10
dd.text((20, y0), "Subtitulo (paragrafo em maiusculas):", font=lab, fill=(40, 40, 40))
bw = (3 * tw + 40 - 4 * 20) // 5
for j, (nome, mk) in enumerate(SUBS):
    caixa = Image.new("RGB", (bw * 3, alt_sub * 3), FUNDO)
    d = ImageDraw.Draw(caixa)
    yy = 70
    for ln in ["50 BOLD & EASY DESIGNS", "FOR ADULTS"]:
        f = mk(92)
        w = sum(d.textlength(c, font=f) for c in ln) + 0.06 * 92 * (len(ln) - 1)
        x = (bw * 3 - w) / 2
        for c in ln:
            d.text((x, yy), c, font=f, fill=CAST); x += d.textlength(c, font=f) + 0.06 * 92
        yy += 120
    d.text((30, alt_sub * 3 - 110), nome, font=F("nunito/Nunito[wght].ttf", 60, [800]), fill=(150, 150, 150))
    fol.paste(caixa.resize((bw, alt_sub), Image.LANCZOS), (20 + j * (bw + 20), y0 + 45))
fol.save(SAIDA)
print("ok", fol.size)
