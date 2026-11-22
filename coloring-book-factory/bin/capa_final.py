#!/usr/bin/env python3
"""Capa final v3 (escolha do board 2026-11-21): capa A creme + titulo 7 (Cherry Bomb One mostarda,
contorno castanho, sombra, letras saltitantes) + subtitulo Fredoka em maiusculas + estrelinhas.
Uso: capa_final.py PASTA_FONTES ARTE.png N_PAGINAS SAIDA_SEM_EXTENSAO MINI1.png MINI2.png ...
Regras KDP (lidas 2026-11-21): bleed 0,125; lombada N x 0,002252 (papel branco); texto na lombada so 80+
paginas, folga 0,0625; texto >= 0,25 pol do corte; area branca do codigo de barras 2 x 1,2 pol a 0,25 pol
da lombada e do corte. So fontes OFL 1.1."""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFont

FT, ARTE, N, SAIDA = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
MINIS = sys.argv[5:]
# textos vem de livro.json["capa"] (env LIVRO_JSON); omissos = piloto Cozy Little Corners
_C = json.load(open(os.environ["LIVRO_JSON"])).get("capa", {}) if os.environ.get("LIVRO_JSON") else {}
TXT = dict(tit1="COZY", tit2="LITTLE CORNERS", sub=["50 BOLD & EASY DESIGNS", "FOR ADULTS"],
           costas_tit="SLOW DOWN AND COLOR", costas_sub="50 cozy little corners to fill with color",
           blurb=("Bold lines and big, simple shapes make every page relaxing and easy to finish "
                  "with markers, colored pencils or gel pens."),
           pontos=["Single-sided pages, so markers never ruin the next design",
                   "Large, simple shapes for relaxing, easy coloring", "Square 8.5 x 8.5 in format"],
           lombada="COZY LITTLE CORNERS")
TXT.update(_C)
PPP, TRIM, BLEED, POL = 300, 8.5, 0.125, 0.002252
px = lambda p: int(round(p * PPP))
FUNDO, CAST, TERRA, MOST = (253, 240, 219), (92, 58, 40), (196, 120, 86), (240, 190, 80)
# modo "sangrar" (capa v4, board 2026-11-22): arte ate a borda, titulo branco DynaPuff com contorno
SANGRAR = TXT.get("modo") == "sangrar"
if SANGRAR:
    FUNDO = tuple(TXT.get("cor_fundo", (222, 238, 252)))       # contracapa
    CAST = tuple(TXT.get("cor_contorno", (31, 58, 95)))         # contorno, textos, lombada
    TERRA = tuple(TXT.get("cor_destaque", (240, 140, 50)))      # estrelas
    MOST = (255, 255, 255)                                      # letras do titulo
SEG = px(0.25)

ANG = [-10, 7, -5, 9, -8, 6, -4, 8, -9, 5, -7, 9, -6, 7]
DY = [0.06, -0.08, 0.04, -0.05, 0.08, -0.06, 0.03, -0.08, 0.06, -0.03, 0.07, -0.06, 0.04, -0.07]
SC = [1.12, 0.94, 1.04, 0.96, 1.08, 0.95, 1.03, 0.97, 1.1, 0.94, 1.05, 0.98, 1.07, 0.95]


def F(path, tam, eixos=None):
    f = ImageFont.truetype(os.path.join(FT, path), max(8, int(tam)))
    if eixos:
        f.set_variation_by_axes(eixos)
    return f


TIT = (lambda t: F("dynapuff/DynaPuff[wdth,wght].ttf", t, [700, 100])) if SANGRAR else \
    (lambda t: F("cherrybombone/CherryBombOne-Regular.ttf", t))
SUBF = lambda t: F("fredoka/Fredoka[wdth,wght].ttf", t, [600, 100])
CORPO = lambda t, w=600: F("nunito/Nunito[wght].ttf", t, [w])


def letras(img, x0, x1, texto, alvo, y, forte=1.0, track=-0.07):
    """Titulo saltitante centrado entre x0 e x1. Devolve (fundo da tinta, caixa real ocupada)."""
    d = ImageDraw.Draw(img)
    util = (x1 - x0) - px(0.2)
    tam = 900
    while True:
        fs = [TIT(tam * (SC[i % len(SC)] if c != " " else 1)) for i, c in enumerate(texto)]
        avs = [d.textlength(c, font=f) for c, f in zip(texto, fs)]
        esp = [0.16 * tam if c == " " else 0 for c in texto]
        tot = sum(avs) + track * tam * (len(texto) - 1) + sum(esp)
        alt = TIT(tam).getbbox(texto.replace(" ", ""))
        if (alt[3] - alt[1]) <= alvo and tot <= util:
            break
        tam -= 8
    asc = TIT(tam).getmetrics()[0]
    x = x0 + ((x1 - x0) - tot) / 2
    s = int(tam * (0.07 if SANGRAR else 0.045))
    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    for i, (c, f) in enumerate(zip(texto, fs)):
        if c != " ":
            pad = int(tam * 0.5)
            lay = Image.new("RGBA", (int(avs[i]) + 2 * pad, int(tam * 1.4) + 2 * pad), (0, 0, 0, 0))
            dl = ImageDraw.Draw(lay)
            base = pad + asc
            dl.text((pad, base + int(tam * 0.06)), c, font=f, fill=CAST, anchor="ls", stroke_width=s, stroke_fill=CAST)
            dl.text((pad, base), c, font=f, fill=MOST, anchor="ls", stroke_width=s, stroke_fill=CAST)
            lay = lay.rotate(ANG[i % len(ANG)] * forte, resample=Image.BICUBIC, expand=False)
            dy = int(DY[i % len(DY)] * forte * (alt[3] - alt[1]))
            camada.alpha_composite(lay, (int(x) - pad, y - pad - alt[1] + dy))
        x += avs[i] + track * tam + esp[i]
    img.paste(camada, (0, 0), camada)
    return y + (alt[3] - alt[1]) + int(0.1 * (alt[3] - alt[1])), camada.getbbox()


def centrado(d, x0, x1, y, txt, f, cor, track=0.0):
    w = sum(d.textlength(c, font=f) for c in txt) + track * f.size * (len(txt) - 1)
    x = x0 + ((x1 - x0) - w) / 2
    for c in txt:
        d.text((x, y), c, font=f, fill=cor); x += d.textlength(c, font=f) + track * f.size


def estrela(d, cx, cy, r, cor):
    d.polygon([(cx + (r if k % 2 == 0 else r * 0.32) * math.cos(math.pi / 4 * k - math.pi / 2),
                cy + (r if k % 2 == 0 else r * 0.32) * math.sin(math.pi / 4 * k - math.pi / 2)) for k in range(8)], fill=cor)


lomb = N * POL
W, H = px(BLEED + TRIM + lomb + TRIM + BLEED), px(BLEED + TRIM + BLEED)
xl0, xl1 = px(BLEED + TRIM), px(BLEED + TRIM + lomb)
capa = Image.new("RGB", (W, H), FUNDO)
d = ImageDraw.Draw(capa)

# ---------- frente ----------
fx0, fx1 = xl1 + SEG, xl1 + px(TRIM) - SEG  # zona segura da frente
arte = Image.open(ARTE).convert("RGB")
if SANGRAR:
    # arte quadrada ate a borda: cobre frente + bleed (W - xl1) x H, centrada na horizontal
    lf = W - xl1
    a = arte.resize((max(lf, H), max(lf, H)), Image.LANCZOS)
    capa.paste(a.crop(((a.width - lf) // 2, (a.height - H) // 2, (a.width - lf) // 2 + lf, (a.height - H) // 2 + H)), (xl1, 0))
    if min(arte.size) < 0.95 * max(lf, H):
        print(f"AVISO: arte {arte.size} abaixo de {max(lf, H)} px (menos de 300 ppi)", file=sys.stderr)
    m = px(0.2)  # folga extra: contorno grosso e letras rodadas
    y, cx1 = letras(capa, fx0 + m, fx1 - m, TXT["tit1"], px(1.3), px(BLEED) + px(0.5), forte=0.7, track=-0.05)
    y, cx2 = letras(capa, fx0 + m, fx1 - m, TXT["tit2"], px(0.6), y + px(0.02), forte=0.42, track=-0.05)
    fs = SUBF(70)
    txt = " ".join(TXT["sub"])
    w = d.textlength(txt, font=fs)
    x = xl1 + (px(TRIM) - w) / 2; ys = y + px(0.1)
    d.rounded_rectangle([x - 40, ys - 14, x + w + 40, ys + 86], radius=50, fill=(255, 255, 255))
    d.text((x, ys), txt, font=fs, fill=CAST)
else:
    lado = px(5.2)
    from PIL import ImageFilter
    mask = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mask).rectangle([int(lado * 0.03)] * 2 + [lado - int(lado * 0.03)] * 2, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(lado * 0.012))  # borda suave: a arte funde-se no fundo
    capa.paste(arte.resize((lado, lado), Image.LANCZOS), (xl1 + (px(TRIM) - lado) // 2, H - px(BLEED) - px(0.1) - lado), mask)
    y, cx1 = letras(capa, fx0, fx1, TXT["tit1"], px(1.25), px(BLEED) + px(0.45))
    y, cx2 = letras(capa, fx0, fx1, TXT["tit2"], px(0.55), y + px(0.05), forte=0.6, track=-0.05)
    ys = y + px(0.12)
    for ln in TXT["sub"]:
        centrado(d, xl1, xl1 + px(TRIM), ys, ln, SUBF(84), CAST, 0.05); ys += 96
    for ex, ey, r in [(0.12, 0.07, 70), (0.87, 0.1, 55), (0.91, 0.2, 35), (0.09, 0.19, 40)]:
        estrela(d, xl1 + ex * px(TRIM), ey * H, r, TERRA)

# ---------- contracapa ----------
bx0, bx1 = px(BLEED), px(BLEED + TRIM)
y = px(BLEED) + px(0.7)
centrado(d, bx0, bx1, y, TXT["costas_tit"], SUBF(96), CAST, 0.05); y += 120
centrado(d, bx0, bx1, y, TXT["costas_sub"], CORPO(56, 700), TERRA); y += 110
texto = TXT["blurb"]
f = CORPO(52)
lin, at = [], ""
for p in texto.split():
    t = (at + " " + p).strip()
    if d.textlength(t, font=f) <= px(TRIM) - 2 * px(0.9): at = t
    else: lin.append(at); at = p
lin.append(at)
for l in lin:
    centrado(d, bx0, bx1, y, l, f, CAST); y += 74
mini, gap = px(1.7), px(0.2)
tot = len(MINIS) * mini + (len(MINIS) - 1) * gap
mx, my = bx0 + (px(TRIM) - tot) // 2, y + px(0.25)
for i, s in enumerate(MINIS):
    m = Image.open(s).convert("RGB")
    mg = int(m.width * 0.375 / 8.5)  # tira a margem branca da pagina
    m = m.crop((mg, mg, m.width - mg, m.height - mg)).resize((mini, mini), Image.LANCZOS)
    d.rounded_rectangle([mx - 12, my - 12, mx + mini + 12, my + mini + 12], radius=26, fill=(255, 255, 255), outline=CAST, width=5)
    capa.paste(m, (mx, my)); mx += mini + gap
y = my + mini + px(0.4)
for txt in TXT["pontos"]:
    fb = CORPO(50, 700)
    w = d.textlength(txt, font=fb)
    x = bx0 + (px(TRIM) - w - 70) / 2
    estrela(d, x + 22, y + 30, 24, TERRA)
    d.text((x + 70, y), txt, font=fb, fill=CAST); y += 78
# codigo de barras: branco 2 x 1,2 pol, 0,25 pol da lombada e do corte inferior
bb1 = xl0 - px(0.25); bby1 = px(BLEED + TRIM) - px(0.25)
barcode = [bb1 - px(2.0), bby1 - px(1.2), bb1, bby1]
d.rectangle(barcode, fill=(255, 255, 255))

# ---------- lombada ----------
d.rectangle([xl0, 0, xl1, H], fill=CAST)
if N >= 80:
    folga = px(0.0625)
    alt = (xl1 - xl0) - 2 * folga
    fsp = TIT(int(alt * 0.85))
    txt = TXT["lombada"]
    b = d.textbbox((0, 0), txt, font=fsp)
    faixa = Image.new("RGBA", (b[2] - b[0] + 4, b[3] - b[1] + 4), (0, 0, 0, 0))
    ImageDraw.Draw(faixa).text((-b[0] + 2, -b[1] + 2), txt, font=fsp, fill=MOST)
    faixa = faixa.rotate(-90, expand=True)
    capa.paste(faixa, (xl0 + ((xl1 - xl0) - faixa.width) // 2, (H - faixa.height) // 2), faixa)

capa.save(SAIDA + "-preview.png", dpi=(PPP, PPP))
try:
    capa.save(SAIDA + ".pdf", resolution=PPP)
except KeyError:  # Pillow sem JPEG (Mac principal): PDF gerado depois com sips
    pass
seguro_frente = [fx0, px(BLEED) + SEG, fx1, H - px(BLEED) - SEG]
dentro = lambda bx: bx[0] >= seguro_frente[0] and bx[2] <= seguro_frente[2] and bx[1] >= seguro_frente[1]
print(json.dumps({"lombada_pol": round(lomb, 4), "tamanho_pol": [round(W / PPP, 4), round(H / PPP, 4)],
                  "titulo_dentro_zona_segura": dentro(cx1) and dentro(cx2), "caixas_titulo": [list(cx1), list(cx2)], "zona_segura": seguro_frente,
                  "fundo_contracapa_px": y, "topo_codigo_barras_px": barcode[1],
                  "texto_lombada": N >= 80}))
