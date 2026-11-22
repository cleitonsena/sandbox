#!/usr/bin/env python3
"""Capa v2: 3 variacoes de design para o board escolher (2026-11-21).

Uso: capa_v2.py PASTA_LIVRO N_PAGINAS
Le PASTA/kit/variacoes/arte-{a,b,c}.png e grava capa-{a,b,c}.pdf + preview.
Mesmas regras KDP do montar.py (bleed 0,125; lombada N x 0,002252; texto lombada so 80+;
texto >= 0,25 pol dentro do corte; area branca do codigo de barras 2 x 1,2 pol).
Fontes: so OFL 1.1 em ~/livros/fontes (licenca verificada no OFL.txt de cada uma).
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

PPP, TRIM, BLEED, POL_POR_PAG = 300, 8.5, 0.125, 0.002252
px = lambda pol: int(round(pol * PPP))
FT = os.path.expanduser("~/livros/fontes")


def fonte(nome, tam, eixos=None):
    caminhos = {
        "cherry": "cherrybombone/CherryBombOne-Regular.ttf",
        "lilita": "lilitaone/LilitaOne-Regular.ttf",
        "fraunces": "fraunces/Fraunces[SOFT,WONK,opsz,wght].ttf",
        "nunito": "nunito/Nunito[wght].ttf",
    }
    f = ImageFont.truetype(os.path.join(FT, caminhos[nome]), tam)
    if eixos:
        f.set_variation_by_axes(eixos)
    return f


def larg(d, t, f, s=0):
    b = d.textbbox((0, 0), t, font=f, stroke_width=s)
    return b[2] - b[0]


VAR = {
    "a": dict(nome="Creme, titulo redondo", fundo=(253, 240, 219), lombada=(196, 120, 86),
              tit=("cherry", None), tit_cor=(92, 58, 40), tit_stroke=None,
              sub_cor=(196, 120, 86), txt=(92, 58, 40), txt_lomb=(255, 248, 240), arte="vinheta"),
    "b": dict(nome="Noite, titulo bloco", fundo=(57, 39, 56), lombada=(247, 196, 107),
              tit=("lilita", None), tit_cor=(255, 236, 200), tit_stroke=(30, 20, 30),
              sub_cor=(247, 196, 107), txt=(255, 236, 200), txt_lomb=(57, 39, 56), arte="vinheta"),
    "c": dict(nome="Arte inteira, serifa suave", fundo=(251, 227, 151), lombada=(92, 58, 40),
              tit=("fraunces", [72, 800, 100, 0]), tit_cor=(92, 58, 40), tit_stroke=None,
              sub_cor=(179, 93, 30), txt=(92, 58, 40), txt_lomb=(251, 227, 151), arte="inteira"),
}

pasta = os.path.abspath(sys.argv[1])
n = int(sys.argv[2])
livro = json.load(open(os.path.join(pasta, "livro.json")))
estado = json.load(open(os.path.join(pasta, "estado.json")))
vdir = os.path.join(pasta, "kit", "variacoes")
amostras = [estado[p["id"]]["tentativas"][-1]["ficheiro"] for p in livro["paginas"]
            if estado.get(p["id"], {}).get("estado") == "aprovada"][:4]

lomb = n * POL_POR_PAG
W, H = px(BLEED + TRIM + lomb + TRIM + BLEED), px(BLEED + TRIM + BLEED)
xl0, xl1 = px(BLEED + TRIM), px(BLEED + TRIM + lomb)
seguro = px(0.25)
res = {}

for k, v in VAR.items():
    capa = Image.new("RGB", (W, H), v["fundo"])
    d = ImageDraw.Draw(capa)
    arte = Image.open(os.path.join(vdir, f"arte-{k}.png")).convert("RGB")
    larg_frente = W - xl1  # da lombada ao bleed exterior
    # --- arte da frente ---
    if v["arte"] == "inteira":
        lado = max(larg_frente, H)
        a = arte.resize((lado, lado), Image.LANCZOS)
        a = a.crop(((lado - larg_frente) // 2, (lado - H) // 2, (lado - larg_frente) // 2 + larg_frente, (lado - H) // 2 + H))
        capa.paste(a, (xl1, 0))
        ppi_arte = round(arte.width / (lado / PPP))
    else:
        lado = px(6.65)
        a = arte.resize((lado, lado), Image.LANCZOS)
        capa.paste(a, (xl1 + (px(TRIM) - lado) // 2, H - px(BLEED) - px(0.1) - lado))
        ppi_arte = round(arte.width / (lado / PPP))
    # --- titulo e subtitulo (frente) ---
    cx0, cx1 = xl1 + seguro, xl1 + px(TRIM) - seguro
    st = 10 if v["tit_stroke"] else 0
    tam = 300
    while True:
        ft = fonte(v["tit"][0], tam, v["tit"][1])
        if larg(d, livro["titulo"], ft, st) <= (cx1 - cx0) - px(0.3):
            break
        tam -= 6
    tw = larg(d, livro["titulo"], ft, st)
    y_tit = px(BLEED) + px(0.4)
    d.text((cx0 + ((cx1 - cx0) - tw) // 2, y_tit), livro["titulo"], font=ft, fill=v["tit_cor"],
           stroke_width=st, stroke_fill=v["tit_stroke"])
    alt_tit = d.textbbox((0, y_tit), livro["titulo"], font=ft, stroke_width=st)[3]
    sub = "50 Bold & Easy Designs for Adults"
    fs = fonte("nunito", 78, [800])
    sw = larg(d, sub, fs)
    d.text((cx0 + ((cx1 - cx0) - sw) // 2, alt_tit + px(0.12)), sub, font=fs, fill=v["sub_cor"])
    # --- contracapa ---
    xb = px(BLEED)
    fb = fonte("nunito", 54, [600])
    fbb = fonte("nunito", 58, [800])
    y = px(BLEED) + px(0.75)
    blurb = livro["contracapa"][:2]
    for i, par in enumerate(blurb):
        f_ = fbb if i == 0 else fb
        linhas, at = [], ""
        for p in par.split():
            t = (at + " " + p).strip()
            if larg(d, t, f_) <= px(TRIM) - 2 * px(0.8):
                at = t
            else:
                linhas.append(at); at = p
        linhas.append(at)
        for ln in linhas:
            d.text((xb + (px(TRIM) - larg(d, ln, f_)) // 2, y), ln, font=f_, fill=v["txt"]); y += 80
        y += 50
    mini, gap = px(1.7), px(0.2)
    tot = len(amostras) * mini + (len(amostras) - 1) * gap
    mx, my = xb + (px(TRIM) - tot) // 2, y + px(0.15)
    for s in amostras:
        m = Image.open(s).convert("RGB").resize((mini, mini), Image.LANCZOS)
        d.rounded_rectangle([mx - 10, my - 10, mx + mini + 10, my + mini + 10], radius=24, fill=(255, 255, 255))
        capa.paste(m, (mx, my)); mx += mini + gap
    y = my + mini + px(0.35)
    for ln in ["Single-sided pages, so markers never ruin the next design", "Large, simple shapes for relaxing, easy coloring"]:
        f_ = fonte("nunito", 50, [700])
        d.text((xb + (px(TRIM) - larg(d, ln, f_)) // 2, y), ln, font=f_, fill=v["txt"]); y += 72
    # codigo de barras: branco 2 x 1,2 pol, 0,25 pol da lombada e do corte inferior
    bx1 = xl0 - px(0.25); by1 = px(BLEED + TRIM) - px(0.25)
    d.rectangle([bx1 - px(2.0), by1 - px(1.2), bx1, by1], fill=(255, 255, 255))
    # --- lombada ---
    d.rectangle([xl0, 0, xl1, H], fill=v["lombada"])
    if n >= 80:
        folga = px(0.0625)
        alt = (xl1 - xl0) - 2 * folga
        fsp = fonte(v["tit"][0], max(10, int(alt * 0.85)), v["tit"][1])
        txt = livro["titulo"].upper()
        bb = d.textbbox((0, 0), txt, font=fsp)
        faixa = Image.new("RGBA", (bb[2] - bb[0] + 4, bb[3] - bb[1] + 4), (0, 0, 0, 0))
        ImageDraw.Draw(faixa).text((-bb[0] + 2, -bb[1] + 2), txt, font=fsp, fill=v["txt_lomb"])
        faixa = faixa.rotate(-90, expand=True)
        capa.paste(faixa, (xl0 + ((xl1 - xl0) - faixa.width) // 2, (H - faixa.height) // 2), faixa)
    capa.save(os.path.join(vdir, f"capa-{k}.pdf"), resolution=PPP)
    capa.save(os.path.join(vdir, f"capa-{k}-preview.png"))
    res[k] = {"nome": v["nome"], "titulo_pt": tam, "ppi_efetivo_arte": ppi_arte}

# folha comparativa
th = 700
fol = Image.new("RGB", (int(W * th / H) + 40, 3 * th + 80), (120, 120, 120))
for i, k in enumerate("abc"):
    im = Image.open(os.path.join(vdir, f"capa-{k}-preview.png"))
    fol.paste(im.resize((int(W * th / H), th)), (20, 20 + i * (th + 20)))
fol.save(os.path.join(vdir, "comparar-capas.png"))
print(json.dumps({"lombada_pol": round(lomb, 4), "px": [W, H], "variacoes": res}))
