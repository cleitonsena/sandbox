#!/usr/bin/env python3
"""Monta o interior PDF e a capa PDF de um livro de colorir (KDP paperback, sem bleed no interior).

Uso:
  montar.py interior PASTA             -> PASTA/kit/interior.pdf
  montar.py capa PASTA ARTE.png [N]    -> PASTA/kit/capa.pdf (N = paginas do livro; omisso = paginas do interior)

Regras (paginas oficiais KDP lidas em 2026-11-21: GVBQ3CMEQW3W2VL6, G201857950, G201953020, G5HDYGP4BXLX4RUW):
- Interior sem bleed: pagina = trim 8,5 x 8,5 pol. Margens minimas: interior 0,375 pol (24-150 pags), resto 0,25 pol.
  Usamos 0,375 pol em todos os lados.
- 300 ppp minimo. Capa: um PDF unico (contracapa + lombada + capa), bleed 0,125 pol em cima, baixo e fora.
- Lombada papel branco tinta preta: paginas x 0,002252 pol. Texto na lombada so com 79+ paginas, 0,0625 pol de folga.
- Texto da capa pelo menos 0,25 pol dentro do corte. Codigo de barras: area branca 2 x 1,2 pol,
  pelo menos 0,25 pol da lombada e do corte (KDP coloca o codigo se nao fornecermos).
Nada publica: so gera ficheiros.
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

PPP = 300
TRIM = 8.5
MARGEM = 0.375
BLEED = 0.125
POL_POR_PAG = 0.002252
F_TIT = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
F_TXT = "/System/Library/Fonts/Supplemental/Georgia.ttf"
F_TXT_B = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
px = lambda pol: int(round(pol * PPP))

modo, pasta = sys.argv[1], os.path.abspath(sys.argv[2])
livro = json.load(open(os.path.join(pasta, "livro.json")))
estado = json.load(open(os.path.join(pasta, "estado.json")))
kit = os.path.join(pasta, "kit")
os.makedirs(kit, exist_ok=True)
lado = px(TRIM)


def fonte(path, tam):
    return ImageFont.truetype(path, tam)


def texto_centrado(d, y, txt, f, largura, cor=0):
    w = d.textbbox((0, 0), txt, font=f)[2]
    d.text(((largura - w) // 2, y), txt, font=f, fill=cor)


def quebrar(d, txt, f, largura_max):
    linhas, atual = [], ""
    for p in txt.split():
        t = (atual + " " + p).strip()
        if d.textbbox((0, 0), t, font=f)[2] <= largura_max:
            atual = t
        else:
            linhas.append(atual); atual = p
    return linhas + [atual]


def pagina_imagem(src):
    util = lado - 2 * px(MARGEM)
    im = Image.open(src).convert("L").resize((util, util), Image.LANCZOS)
    tela = Image.new("L", (lado, lado), 255)
    tela.paste(im, (px(MARGEM), px(MARGEM)))
    return tela.point(lambda v: 255 if v > 150 else 0).convert("1")


def aprovadas():
    out = []
    for pg in livro["paginas"]:
        st = estado.get(pg["id"], {})
        if st.get("estado") == "aprovada":
            out.append(st["tentativas"][-1]["ficheiro"])
    return out


if modo == "interior":
    paginas = []
    # 1. titulo
    p = Image.new("L", (lado, lado), 255); d = ImageDraw.Draw(p)
    texto_centrado(d, px(3.0), livro["titulo"], fonte(F_TIT, 150), lado)
    texto_centrado(d, px(3.8), livro["subtitulo"], fonte(F_TXT, 60), lado)
    paginas.append(p)
    # 2. copyright e dica
    p = Image.new("L", (lado, lado), 255); d = ImageDraw.Draw(p)
    f = fonte(F_TXT, 40)
    y = px(5.6)
    for par in livro["copyright"]:
        for linha in quebrar(d, par, f, lado - 2 * px(1.0)):
            texto_centrado(d, y, linha, f, lado); y += 56
        y += 40
    paginas.append(p)
    # 3. paginas de colorir, cada uma seguida de verso branco (marcadores nao passam para o desenho seguinte)
    for src in aprovadas():
        paginas.append(pagina_imagem(src))
        paginas.append(Image.new("1", (lado, lado), 1))
    destino = os.path.join(kit, "interior.pdf")
    paginas[0].save(destino, save_all=True, append_images=paginas[1:], resolution=PPP)
    json.dump({"paginas_interior": len(paginas)}, open(os.path.join(kit, "interior.json"), "w"))
    print(json.dumps({"interior": destino, "paginas": len(paginas), "minimo_kdp": 24}))

elif modo == "capa":
    arte = sys.argv[3]
    n = int(sys.argv[4]) if len(sys.argv) > 4 else json.load(open(os.path.join(kit, "interior.json")))["paginas_interior"]
    lombada = n * POL_POR_PAG
    W = px(BLEED + TRIM + lombada + TRIM + BLEED)
    H = px(BLEED + TRIM + BLEED)
    fundo = tuple(livro["cor_fundo"])
    tinta = tuple(livro["cor_texto"])
    capa = Image.new("RGB", (W, H), fundo)
    d = ImageDraw.Draw(capa)
    x_lomb0 = px(BLEED + TRIM)            # inicio da lombada
    x_lomb1 = px(BLEED + TRIM + lombada)  # fim da lombada = inicio da capa
    x_frente = x_lomb1
    seguro = px(0.25)
    # --- capa (frente) ---
    painel = px(6.4)  # 1920 px a 300 ppp
    art = Image.open(arte).convert("RGB").resize((painel, painel), Image.LANCZOS)
    cx = x_frente + (px(TRIM) - painel) // 2
    topo = px(BLEED) + px(1.75)
    d.rectangle([cx - 12, topo - 12, cx + painel + 12, topo + painel + 12], fill=(255, 255, 255))
    capa.paste(art, (cx, topo))
    larg_frente = px(TRIM) - 2 * seguro
    def centro_frente(y, txt, f):
        w = d.textbbox((0, 0), txt, font=f)[2]
        d.text((x_frente + (px(TRIM) - w) // 2, y), txt, font=f, fill=tinta)
    ft = fonte(F_TIT, 170)
    while d.textbbox((0, 0), livro["titulo"], font=ft)[2] > larg_frente:
        ft = fonte(F_TIT, ft.size - 6)
    centro_frente(px(BLEED) + px(0.45), livro["titulo"], ft)
    centro_frente(px(BLEED) + px(1.2), livro["subtitulo"], fonte(F_TXT_B, 64))
    # --- contracapa ---
    x_tras = px(BLEED)
    f = fonte(F_TXT, 52)
    y = px(BLEED) + px(0.9)
    for par in livro["contracapa"]:
        for linha in quebrar(d, par, f, px(TRIM) - 2 * px(0.75)):
            w = d.textbbox((0, 0), linha, font=f)[2]
            d.text((x_tras + (px(TRIM) - w) // 2, y), linha, font=f, fill=tinta); y += 72
        y += 40
    # miniaturas das paginas (amostra)
    mini = px(1.55)
    fontes_mini = aprovadas()[:4]
    gap = px(0.25)
    total = len(fontes_mini) * mini + (len(fontes_mini) - 1) * gap
    mx = x_tras + (px(TRIM) - total) // 2
    my = y + px(0.2)
    for s in fontes_mini:
        m = Image.open(s).convert("RGB").resize((mini, mini), Image.LANCZOS)
        d.rectangle([mx - 6, my - 6, mx + mini + 6, my + mini + 6], fill=(255, 255, 255))
        capa.paste(m, (mx, my)); mx += mini + gap
    # area do codigo de barras: branca, 2 x 1,2 pol, 0,25 pol da lombada e do corte inferior
    bx1 = x_lomb0 - px(0.25); bx0 = bx1 - px(2.0)
    by1 = px(BLEED + TRIM) - px(0.25); by0 = by1 - px(1.2)
    d.rectangle([bx0, by0, bx1, by1], fill=(255, 255, 255))
    # --- lombada ---
    d.rectangle([x_lomb0, 0, x_lomb1, H], fill=tuple(livro["cor_lombada"]))
    if n >= 80:  # KDP: 79+ (Cover Creator 80); usamos 80 para ficar seguro
        folga = px(0.0625)
        alt = (x_lomb1 - x_lomb0) - 2 * folga
        fs = fonte(F_TIT, max(10, int(alt * 0.8)))
        txt = livro["titulo"].upper()
        tw, th = d.textbbox((0, 0), txt, font=fs)[2:]
        faixa = Image.new("RGBA", (tw, th + 4), (0, 0, 0, 0))
        ImageDraw.Draw(faixa).text((0, 0), txt, font=fs, fill=tuple(livro["cor_texto_lombada"]))
        faixa = faixa.rotate(-90, expand=True)
        capa.paste(faixa, (x_lomb0 + ((x_lomb1 - x_lomb0) - faixa.width) // 2, (H - faixa.height) // 2), faixa)
    destino = os.path.join(kit, "capa.pdf")
    capa.save(destino, resolution=PPP)
    capa.save(os.path.join(kit, "capa-preview.png"))
    print(json.dumps({"capa": destino, "paginas_usadas": n, "lombada_pol": round(lombada, 4),
                      "largura_pol": round(W / PPP, 4), "altura_pol": round(H / PPP, 4),
                      "texto_lombada": n >= 80, "px": [W, H]}))
