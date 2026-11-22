#!/usr/bin/env python3
"""Folha de provas de tipografia na frente da capa A (creme). So fontes OFL 1.1 em ~/livros/fontes."""
import os, sys
from PIL import Image, ImageDraw, ImageFont

PPP = 300
px = lambda p: int(round(p * PPP))
FT = os.path.expanduser("~/livros/fontes")
arte = Image.open(sys.argv[1]).convert("RGB")
saida = sys.argv[2]
FUNDO, CAST, TERRA, CREME, BRANCO = (253, 240, 219), (92, 58, 40), (196, 120, 86), (255, 248, 236), (255, 255, 255)
W, H = px(8.625), px(8.75)  # frente com bleed exterior, cima e baixo
SEG = px(0.25)


def F(path, tam, eixos=None):
    f = ImageFont.truetype(os.path.join(FT, path), tam)
    if eixos:
        f.set_variation_by_axes(eixos)
    return f


def medir(d, t, f, s, track):
    if not track:
        b = d.textbbox((0, 0), t, font=f, stroke_width=s); return b[2] - b[0], b
    w = sum(d.textlength(c, font=f) for c in t) + track * (len(t) - 1) + 2 * s
    b = d.textbbox((0, 0), t, font=f, stroke_width=s)
    return int(w), b


def linha(img, y, t, f, cor, s=0, scor=None, sombra=None, track=0, maxw=None):
    """Desenha uma linha centrada (dentro de 0,25 pol); encolhe se passar de maxw. Devolve y do fundo."""
    d = ImageDraw.Draw(img)
    maxw = maxw or (W - px(0.125) - 2 * SEG)  # zona util: corte a corte menos 0,25 pol
    while medir(d, t, f, s, track)[0] > maxw:
        f = f.font_variant(size=f.size - 4)
    w, b = medir(d, t, f, s, track)
    x0 = (W - px(0.125) - w) // 2  # centrado no corte (o bleed exterior fica a direita)
    camadas = []
    if sombra:
        camadas.append((sombra[0], sombra[1], sombra[2]))
    camadas.append((0, 0, cor))
    for dx, dy, c in camadas:
        if track:
            x = x0 + s
            for ch in t:
                d.text((x + dx, y - b[1] + dy), ch, font=f, fill=c, stroke_width=s, stroke_fill=scor if c == cor else c)
                x += d.textlength(ch, font=f) + track
        else:
            d.text((x0 - b[0] + dx, y - b[1] + dy), t, font=f, fill=c, stroke_width=s, stroke_fill=scor if c == cor else c)
    return y + (b[3] - b[1])


def base():
    im = Image.new("RGB", (W, H), FUNDO)
    lado = px(6.65)
    im.paste(arte.resize((lado, lado), Image.LANCZOS), ((W - px(0.125) - lado) // 2, H - px(0.225) - lado))
    return im


SUB = "50 Bold & Easy Designs for Adults"
fsub = lambda tam=78: F("nunito/Nunito[wght].ttf", tam, [800])
y0 = px(0.125) + px(0.35)
provas = []

def p1(im):  # atual
    y = linha(im, y0, "Cozy Little Corners", F("cherrybombone/CherryBombOne-Regular.ttf", 246), CAST)
    linha(im, y + px(0.12), SUB, fsub(), TERRA)
provas.append(("1 Atual: Cherry Bomb One", p1))

def p2(im):
    y = linha(im, y0, "Cozy", F("caprasimo/Caprasimo-Regular.ttf", 420), CAST, s=12, scor=CREME, sombra=(14, 14, TERRA))
    y = linha(im, y + px(0.02), "Little Corners", F("caprasimo/Caprasimo-Regular.ttf", 200), CAST, s=10, scor=CREME, sombra=(10, 10, TERRA))
    linha(im, y + px(0.1), SUB, fsub(66), TERRA)
provas.append(("2 Caprasimo, empilhado, sombra", p2))

def p3(im):
    y = linha(im, y0, "Cozy Little Corners", F("shrikhand/Shrikhand-Regular.ttf", 240), TERRA, sombra=(12, 12, CAST))
    linha(im, y + px(0.14), SUB, fsub(), CAST)
provas.append(("3 Shrikhand, retro", p3))

def p4(im):
    f = lambda t: F("dynapuff/DynaPuff[wdth,wght].ttf", t, [700, 100])
    y = linha(im, y0, "Cozy", f(400), CAST, s=22, scor=BRANCO)
    y = linha(im, y - px(0.02), "Little Corners", f(210), CAST, s=18, scor=BRANCO)
    linha(im, y + px(0.1), SUB, fsub(66), TERRA)
provas.append(("4 DynaPuff, autocolante", p4))

def p5(im):
    f = lambda t: F("titanone/TitanOne-Regular.ttf", t)
    y = linha(im, y0, "COZY", f(380), TERRA, track=20, sombra=(0, 14, CAST))
    y = linha(im, y + px(0.04), "LITTLE CORNERS", f(170), CAST, track=14)
    linha(im, y + px(0.12), SUB, fsub(66), TERRA)
provas.append(("5 Titan One, maiusculas", p5))

def p6(im):
    f = lambda t: F("bagelfatone/BagelFatOne-Regular.ttf", t)
    y = linha(im, y0, "Cozy", f(400), TERRA, s=12, scor=CAST)
    y = linha(im, y + px(0.02), "Little Corners", f(200), TERRA, s=9, scor=CAST)
    linha(im, y + px(0.1), SUB, fsub(66), CAST)
provas.append(("6 Bagel Fat One, contorno", p6))

def p7(im):
    y = linha(im, y0 - px(0.1), "Cozy", F("pacifico/Pacifico-Regular.ttf", 400), TERRA)
    y = linha(im, y - px(0.05), "LITTLE CORNERS", F("fredoka/Fredoka[wdth,wght].ttf", 170, [600, 100]), CAST, track=24)
    linha(im, y + px(0.12), SUB, fsub(66), TERRA)
provas.append(("7 Pacifico + Fredoka", p7))

def p8(im):
    y = linha(im, y0, "Cozy Little", F("youngserif/YoungSerif-Regular.ttf", 230), CAST)
    y = linha(im, y + px(0.02), "Corners", F("youngserif/YoungSerif-Regular.ttf", 230), CAST)
    linha(im, y + px(0.12), SUB.upper(), F("nunito/Nunito[wght].ttf", 54, [800]), TERRA, track=6)
provas.append(("8 Young Serif, livro", p8))

def p9(im):
    f = lambda t: F("gluten/Gluten[slnt,wght].ttf", t, [800, 0])
    y = linha(im, y0, "Cozy Little", f(250), CAST, sombra=(0, 10, TERRA))
    y = linha(im, y - px(0.02), "Corners", f(250), CAST, sombra=(0, 10, TERRA))
    linha(im, y + px(0.1), SUB, fsub(66), TERRA)
provas.append(("9 Gluten, desenhada a mao", p9))

th = 760
tw = int(W * th / H)
lab = F("nunito/Nunito[wght].ttf", 30, [800])
fol = Image.new("RGB", (3 * tw + 80, 3 * (th + 50) + 30), (235, 235, 235))
for i, (nome, fn) in enumerate(provas):
    im = base(); fn(im)
    x, y = 20 + (i % 3) * (tw + 20), 20 + (i // 3) * (th + 50)
    ImageDraw.Draw(fol).text((x, y), nome, font=lab, fill=(40, 40, 40))
    fol.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 40))
fol.save(saida)
print("ok", fol.size)
