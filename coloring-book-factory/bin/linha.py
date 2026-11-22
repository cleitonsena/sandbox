#!/usr/bin/env python3
"""Linha de montagem de um livro de colorir (piloto, decisao do board 2026-11-21).

Uso: linha.py PASTA_DO_LIVRO
A pasta tem livro.json: {"estilo": "...{tema}...", "tamanho": "1024x1024",
"paginas": [{"id": "p01", "tema": "..."}]}
Para cada pagina: gerar -> checagem automatica -> revisor (codex, subscricao) ->
aprovada? vetoriza/amplia : refaz a MESMA pagina (max 3) -> fila humana.
Estado em estado.json: se parar, retoma onde ficou. Nada publica, nada abre a Amazon.
"""
import json, os, subprocess, sys, time
from PIL import Image

BIN = os.path.expanduser("~/livros/bin")
MAX_TENTATIVAS = 3
CUSTO_IMG = 0.02  # medido 2026-11-21: US$ 0,06 por 3 imagens
LADO_IMPRESSAO = 2550  # 8,5 pol x 300 ppp

pasta = os.path.abspath(sys.argv[1]) if not sys.argv[1].startswith("--") else os.getcwd()
f_estado = os.path.join(pasta, "estado.json")
estado = json.load(open(f_estado)) if os.path.exists(f_estado) else {}
if not sys.argv[1].startswith("--"):
    os.makedirs(os.path.join(pasta, "tentativas"), exist_ok=True)
    os.makedirs(os.path.join(pasta, "final"), exist_ok=True)


def gravar():
    with open(f_estado, "w") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1)


def checagem(path):
    """Regras medidas no pixel. Devolve lista de problemas (vazia = ok)."""
    im = Image.open(path).convert("L")
    w, h = im.size
    px = im.load()
    total = w * h
    hist = im.histogram()
    cinza = sum(hist[40:216]) / total
    preto = sum(hist[:40]) / total
    probs = []
    if cinza > 0.06:
        probs.append(f"too much gray or shading ({cinza:.0%} gray pixels); use pure black lines on pure white")
    if preto > 0.30:
        probs.append(f"too much solid black ({preto:.0%}); keep large white areas to color")
    if preto < 0.02:
        probs.append("lines too thin or too few; use thick bold outlines")
    # moldura de pagina = linha longa escura perto da borda em pelo menos 3 lados
    # (1 ou 2 lados = conteudo, ex.: prateleira ou janela; calibrado no piloto 01)
    lados = 0
    for nome in ("top", "bottom", "left", "right"):
        for frac in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06):
            if nome == "top": linha = [px[x, int(h * frac)] for x in range(w)]
            elif nome == "bottom": linha = [px[x, int(h * (1 - frac))] for x in range(w)]
            elif nome == "left": linha = [px[int(w * frac), y] for y in range(h)]
            else: linha = [px[int(w * (1 - frac)), y] for y in range(h)]
            if sum(1 for v in linha if v < 100) / len(linha) > 0.6:
                lados += 1
                break
    if lados >= 3:
        probs.append("there is a rectangular border or frame around the page; remove it")
    # margem: em cada lado, a banda externa de 1,5% deve ser quase toda branca
    b = max(2, int(w * 0.015))
    bandas = {
        "top": [px[x, y] for x in range(w) for y in range(b)],
        "bottom": [px[x, y] for x in range(w) for y in range(h - b, h)],
        "left": [px[x, y] for y in range(h) for x in range(b)],
        "right": [px[x, y] for y in range(h) for x in range(w - b, w)],
    }
    cortados = [n for n, v in bandas.items() if sum(1 for p_ in v if p_ < 100) / len(v) > 0.06]
    if cortados:
        probs.append("objects are cut off by the page edge (" + ", ".join(cortados) + "); keep the whole drawing inside with a white margin")
    return probs


ESQUEMA = {"type": "object", "additionalProperties": False,
           "required": ["defeitos", "sugestoes", "nota"],
           "properties": {"defeitos": {"type": "array", "items": {"type": "string"}},
                          "sugestoes": {"type": "array", "items": {"type": "string"}},
                          "nota": {"type": "integer"}}}


def revisor(path, tema):
    f_esq = os.path.join(pasta, "esquema-revisor.json")
    json.dump(ESQUEMA, open(f_esq, "w"))
    f_out = path + ".revisao.json"
    pedido = (
        "You are the quality reviewer of an adult coloring book (cozy, bold and easy style). "
        f"Look at the attached page. Intended theme: {tema}. "
        "A DEFECT is only one of these: 1) theme not recognisable; 2) gray shading or filled areas instead of outlines; "
        "3) any text, letters, numbers or watermark; 4) deformed hands, faces, animals or objects; "
        "5) many areas too tiny to color with a fine marker; 6) a border or frame around the page; "
        "7) main objects cut off by the page edge; 8) anything resembling a known brand, logo or copyrighted character. "
        "Everything else (could be simpler, could be nicer) is a SUGGESTION, not a defect. "
        "Be fair: a clean, usable page with no defects must pass even if it could be improved. "
        "Score 1-10. Write each defect and suggestion as a short instruction in English for the illustrator. "
        "Do not run any commands; just look at the image and answer."
    )
    cmd = ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "-i", path,
           "--output-schema", f_esq, "-o", f_out, pedido]
    env = dict(os.environ, PATH="/opt/homebrew/bin:" + os.path.expanduser("~/.local/bin") + ":" + os.environ["PATH"])
    t0 = time.time()
    r = subprocess.run(cmd, cwd=pasta, capture_output=True, text=True, timeout=600, env=env, stdin=subprocess.DEVNULL)
    try:
        out = json.load(open(f_out))
    except Exception:
        return {"aprovada": False, "nota": 0, "defeitos": [], "problemas": ["revisor falhou: " + r.stderr[-300:]],
                "segundos": round(time.time() - t0, 1), "erro_revisor": True}
    out["segundos"] = round(time.time() - t0, 1)
    out["aprovada"] = not out.get("defeitos")
    out["problemas"] = out.get("defeitos", [])
    return out


MARGEM_SEGURA = 113  # 0,375 pol a 300 ppp (margem interna KDP 24-150 pags, verificado 2026-11-21)


def ampliar(src, dst):
    """Amplia para 2550x2550 a 300 ppp, 1 bit, com margem branca de seguranca."""
    lado = LADO_IMPRESSAO - 2 * MARGEM_SEGURA
    im = Image.open(src).convert("L").resize((lado, lado), Image.LANCZOS)
    tela = Image.new("L", (LADO_IMPRESSAO, LADO_IMPRESSAO), 255)
    tela.paste(im, (MARGEM_SEGURA, MARGEM_SEGURA))
    tela.point(lambda v: 255 if v > 150 else 0).convert("1").save(dst, dpi=(300, 300))


if sys.argv[1] == "--checar":  # testa as regras em imagens ja feitas, sem gerar nada
    import glob
    for f in sorted(glob.glob(os.path.join(sys.argv[2], "*.png"))):
        print(os.path.basename(f), checagem(f) or "OK")
    sys.exit(0)
if sys.argv[1] == "--revisar":  # testa so o revisor: --revisar PASTA IMG "tema"
    pasta = os.path.abspath(sys.argv[2])
    print(json.dumps(revisor(os.path.abspath(sys.argv[3]), sys.argv[4]), ensure_ascii=False))
    sys.exit(0)
livro = json.load(open(os.path.join(pasta, "livro.json")))

for pg in livro["paginas"]:
    st = estado.setdefault(pg["id"], {"estado": "pendente", "tentativas": []})
    if st["estado"] in ("aprovada", "fila_humana"):
        continue
    correcoes = list(st.get("correcoes_revisao", []))  # vindas da revisao do livro inteiro
    for t in st["tentativas"]:
        correcoes += t.get("problemas", [])
    while len(st["tentativas"]) < MAX_TENTATIVAS:
        n = len(st["tentativas"]) + 1
        prompt = livro["estilo"].format(tema=pg["tema"])
        if correcoes:
            prompt += " Important corrections: " + "; ".join(dict.fromkeys(correcoes)) + "."
        img = os.path.join(pasta, "tentativas", f"{pg['id']}-t{n}.png")
        g = subprocess.run([sys.executable, os.path.join(BIN, "gerar_imagem.py"), "gpt-image-2", "low", img, prompt],
                           capture_output=True, text=True, env=dict(os.environ, TAMANHO=livro.get("tamanho", "1024x1024")))
        reg = {"n": n, "ficheiro": img, "custo_est": CUSTO_IMG}
        if g.returncode != 0:
            reg.update(etapa="gerar", problemas=[], erro=g.stdout[-300:])
            st["tentativas"].append(reg); gravar()
            print(pg["id"], "t", n, "ERRO gerar", g.stdout[-200:], flush=True)
            continue
        reg["gerar"] = json.loads(g.stdout.strip().splitlines()[-1])
        probs = checagem(img)
        if probs:
            reg.update(etapa="checagem", problemas=probs)
        else:
            rv = revisor(img, pg["tema"])
            reg.update(etapa="revisor", revisor=rv, problemas=rv.get("problemas", []))
            if rv.get("aprovada"):
                ampliar(img, os.path.join(pasta, "final", pg["id"] + ".png"))
                st["estado"] = "aprovada"
        st["tentativas"].append(reg); gravar()
        print(pg["id"], "t", n, reg["etapa"], "OK" if st["estado"] == "aprovada" else "FALHA", reg["problemas"][:3], flush=True)
        if st["estado"] == "aprovada":
            break
        correcoes += reg["problemas"]
    if st["estado"] != "aprovada":
        st["estado"] = "fila_humana"; gravar()

# resumo
tent = sum(len(s["tentativas"]) for s in estado.values())
aprov = [k for k, s in estado.items() if s["estado"] == "aprovada"]
res = {"paginas": len(estado), "aprovadas": len(aprov), "fila_humana": len(estado) - len(aprov),
       "imagens_geradas": tent, "custo_estimado_usd": round(tent * CUSTO_IMG, 3),
       "aprovadas_a_primeira": sum(1 for s in estado.values() if s["estado"] == "aprovada" and len(s["tentativas"]) == 1)}
json.dump(res, open(os.path.join(pasta, "resumo.json"), "w"), indent=1)
print("RESUMO", json.dumps(res), flush=True)
