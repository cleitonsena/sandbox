#!/usr/bin/env python3
"""PDF para imprimir em casa (Gumroad/Etsy): Letter 8.5x11, capa, copyright, 1 desenho por pagina.
Uso: imprimivel.py PASTA_DO_LIVRO  -> PASTA/kit/imprimivel.pdf"""
import glob, json, os, sys
from PIL import Image, ImageDraw, ImageFont
pasta = os.path.abspath(sys.argv[1])
AMOSTRA = int(sys.argv[sys.argv.index("--amostra") + 1]) if "--amostra" in sys.argv else 0
L = json.load(open(f"{pasta}/livro.json"))
est = json.load(open(f"{pasta}/estado.json"))
DPI, W, Hh = 300, 2550, 3300
fonte = sorted(glob.glob(os.path.expanduser("~/livros/fontes/nunito/*.ttf")))[0]
paginas = []
# 1. capa: so a frente, cortada da capa completa (sangria 0.125 pol)
cj = json.load(open(f"{pasta}/kit/capa.json"))
cap = Image.open(f"{pasta}/kit/capa-preview.png").convert("RGB")
b = round(0.125 * DPI)
x0 = round((0.125 + 8.5 + cj["lombada_pol"]) * DPI)
frente = cap.crop((x0, b, cap.width - b, cap.height - b))
frente.thumbnail((W - 2 * 150, W - 2 * 150))
pg = Image.new("RGB", (W, Hh), "white")
pg.paste(frente, ((W - frente.width) // 2, (Hh - frente.height) // 2))
paginas.append(pg)
# 2. copyright e uso pessoal
pg = Image.new("L", (W, Hh), 255); d = ImageDraw.Draw(pg)
f = ImageFont.truetype(fonte, 48)
linhas = L.get("copyright", []) + ([ "", f"Free sample: {AMOSTRA} pages from the full book."] if AMOSTRA else []) + ["", "Printable edition for personal use. Print as many copies as you like for yourself;",
                                    "please do not share or resell the files.", "",
                                    "Best on thick paper (cardstock), printed at 100% / actual size."]
y = 1300
for t in linhas:
    w = d.textlength(t, font=f); d.text(((W - w) / 2, y), t, fill="black", font=f); y += 80
paginas.append(pg)
# 3. desenhos, 1 por pagina, centrados (na amostra: N espalhados pelo livro)
aprov = [p for p in L["paginas"] if est.get(p["id"], {}).get("estado") == "aprovada"]
if AMOSTRA:
    aprov = [aprov[round(i * (len(aprov) - 1) / max(1, AMOSTRA - 1))] for i in range(min(AMOSTRA, len(aprov)))]
for p in aprov:
    im = Image.open(f"{pasta}/final/{p['id']}.png").convert("L")
    pg = Image.new("L", (W, Hh), 255)
    pg.paste(im, ((W - im.width) // 2, (Hh - im.height) // 2))
    paginas.append(pg.point(lambda v: 255 if v > 127 else 0).convert("1"))
saida = f"{pasta}/kit/amostra/amostra.pdf" if AMOSTRA else f"{pasta}/kit/imprimivel.pdf"
os.makedirs(os.path.dirname(saida), exist_ok=True)
paginas[0].save(saida, save_all=True, append_images=paginas[1:], resolution=DPI)
print(json.dumps({"ficheiro": saida, "paginas": len(paginas), "mb": round(os.path.getsize(saida) / 1e6, 1)}))
