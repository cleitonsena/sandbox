#!/usr/bin/env python3
"""PDF to print at home (Gumroad/Etsy): Letter 8.5x11, cover, copyright, 1 design per page.
Usage: printable.py BOOK_FOLDER  -> FOLDER/kit/printable.pdf"""
import glob, json, os, sys
from PIL import Image, ImageDraw, ImageFont
folder = os.path.abspath(sys.argv[1])
SAMPLE = int(sys.argv[sys.argv.index("--sample") + 1]) if "--sample" in sys.argv else 0
L = json.load(open(f"{folder}/book.json"))
st = json.load(open(f"{folder}/state.json"))
DPI, W, Hh = 300, 2550, 3300
font = sorted(glob.glob(os.path.expanduser("~/books/fonts/nunito/*.ttf")))[0]
pages = []
# 1. cover: front only, cropped from the full cover (bleed 0.125 in)
cj = json.load(open(f"{folder}/kit/cover.json"))
cov = Image.open(f"{folder}/kit/cover-preview.png").convert("RGB")
b = round(0.125 * DPI)
x0 = round((0.125 + 8.5 + cj["spine_in"]) * DPI)
front = cov.crop((x0, b, cov.width - b, cov.height - b))
front.thumbnail((W - 2 * 150, W - 2 * 150))
pg = Image.new("RGB", (W, Hh), "white")
pg.paste(front, ((W - front.width) // 2, (Hh - front.height) // 2))
pages.append(pg)
# 2. copyright and personal use
pg = Image.new("L", (W, Hh), 255); d = ImageDraw.Draw(pg)
f = ImageFont.truetype(font, 48)
lines = L.get("copyright", []) + ([ "", f"Free sample: {SAMPLE} pages from the full book."] if SAMPLE else []) + ["", "Printable edition for personal use. Print as many copies as you like for yourself;",
                                    "please do not share or resell the files.", "",
                                    "Best on thick paper (cardstock), printed at 100% / actual size."]
y = 1300
for t in lines:
    w = d.textlength(t, font=f); d.text(((W - w) / 2, y), t, fill="black", font=f); y += 80
pages.append(pg)
# 3. designs, 1 per page, centered (in the sample: N spread across the book)
approved = [p for p in L["pages"] if st.get(p["id"], {}).get("state") == "approved"]
if SAMPLE:  # decision 0024: pages taken from the image bank never go into the free sample
    approved = [p for p in approved if not p.get("origin")] or approved
    approved = [approved[round(i * (len(approved) - 1) / max(1, SAMPLE - 1))] for i in range(min(SAMPLE, len(approved)))]
for p in approved:
    im = Image.open(f"{folder}/final/{p['id']}.png").convert("L")
    pg = Image.new("L", (W, Hh), 255)
    pg.paste(im, ((W - im.width) // 2, (Hh - im.height) // 2))
    pages.append(pg.point(lambda v: 255 if v > 127 else 0).convert("1"))
out = f"{folder}/kit/sample/sample.pdf" if SAMPLE else f"{folder}/kit/printable.pdf"
os.makedirs(os.path.dirname(out), exist_ok=True)
pages[0].save(out, save_all=True, append_images=pages[1:], resolution=DPI)
print(json.dumps({"file": out, "pages": len(pages), "mb": round(os.path.getsize(out) / 1e6, 1)}))
