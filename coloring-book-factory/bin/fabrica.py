#!/usr/bin/env python3
"""Fabrica de livros (decisao 0010). Corre no Air, sozinha, a partir da fila em ~/empresa/fila/.

Uso: fabrica.py            -> processa a fila ate cada tarefa chegar a um portao humano ou acabar
     fabrica.py --estado   -> so reescreve o relatorio e a caixa de decisoes

Tarefas (um .json por tarefa em ~/empresa/fila/, processadas por ordem de nome):
  {"tipo": "livro", "pasta": "~/livros/livro-02"}           (pasta tem livro.json com "pedido")
  {"tipo": "pesquisa", "id": "puzzles-seniores", "keywords": [...], "pergunta": "..."}
Fases do livro: benchmark (capas, desenhos, preco) -> brief -> [portao: brief] -> paginas -> [portao: paginas falhadas] -> interior -> capa
-> ficha -> revisao do livro inteiro (refaz paginas 1 vez sozinha) -> arquivo em ~/Livros-Prontos
-> kit -> retro (sprint review) -> [portao: upload humano] -> feito.
Aprovacoes humanas: <pasta>/aprovacoes.json (escrito no Mac principal depois de o board decidir).
Tetos sem perguntar: US$ 2 por livro, US$ 10 por mes (imagens + Apify).
Nunca publica, nunca abre a Amazon, nunca cria contas, nunca paga.
"""
import datetime, glob, json, math, os, shutil, statistics, subprocess, sys, time

H = os.path.expanduser
EMP, LIV, BIN = H("~/empresa"), H("~/livros"), H("~/livros/bin")
FILA, PEND, REL = f"{EMP}/fila", f"{EMP}/decisoes/pendentes.md", f"{EMP}/relatorios/fabrica.md"
GASTOS = f"{EMP}/gastos.jsonl"
TETO_LIVRO, TETO_MES = 2.0, 10.0
# Regra de preco (decisao 0012). O board muda em ~/empresa/config.json.
# retencao_eua: KDP retem na fonte 30% sem W-8BEN; tratado EUA-Espanha art. 12 limita a 5% (direitos de autor literarios/artisticos).
#   Se o KDP aplica 5% a livros de colorir: NAO VERIFICADO.
# irpf_estimado: IRPF em Espanha cai sobre o lucro (vendas menos gastos), nao sobre cada venda. Taxa marginal NAO VERIFICADO (gestor).
RETENCAO_EUA, IRPF_ESTIMADO = 0.05, 0.30
LICOES, MELHORIAS, CONFIG = f"{LIV}/licoes.md", f"{EMP}/melhorias.md", f"{EMP}/config.json"
CUSTO_IMG, CUSTO_CAPA, CUSTO_APIFY_LIVRO = 0.02, 0.06, 0.006  # medidos 2026-11-21 (saldo OpenAI, run Apify)
ENV = dict(os.environ, PATH=f"/opt/homebrew/bin:{H('~/.local/bin')}:/usr/bin:/bin:/usr/sbin:/sbin")
PY = sys.executable
hoje = lambda: datetime.date.today().isoformat()
pendentes, linhas_rel = [], []


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def lj(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d


def gj(p, d):
    with open(p, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def gasto(desc, usd):
    with open(GASTOS, "a") as f:
        f.write(json.dumps({"data": hoje(), "desc": desc, "usd": round(usd, 4)}, ensure_ascii=False) + "\n")


def gasto_mes():
    m = hoje()[:7]
    tot = 0.0
    if os.path.exists(GASTOS):
        for l in open(GASTOS):
            r = json.loads(l)
            if r["data"].startswith(m):
                tot += r["usd"]
    return tot


def run(cmd, cwd=None, timeout=None, extra=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                          env=dict(ENV, **(extra or {})), stdin=subprocess.DEVNULL)


def alma(nome):
    for b in lj(H("~/.openmausbot/bots.json"), []):
        if b.get("name") == nome:
            return b.get("soul", "")
    return ""


def codex(papel, pedido, esquema, cwd, saida, imagens=()):
    """Chama o bot (Codex CLI, subscricao) em modo so-leitura e devolve o JSON validado pelo esquema."""
    f_esq = saida + ".esquema.json"
    gj(f_esq, esquema)
    texto = (alma(papel) + "\n\n" if alma(papel) else f"Es o {papel}.\n\n") + pedido + \
        "\nNao corras comandos que alterem ficheiros. Responde so com o JSON pedido."
    img = [a for f in imagens for a in ("-i", f)]
    r = run(["codex", "exec", "--skip-git-repo-check", "-s", "read-only"] + img + ["--output-schema", f_esq,
             "-o", saida, texto], cwd=cwd, timeout=1500)
    d = lj(saida)
    if d is None:
        raise RuntimeError(f"{papel} falhou: {r.stderr[-400:]}")
    return d


def portao(tarefa, chave, texto, ficheiros=()):
    pendentes.append({"tarefa": tarefa, "decisao": chave, "texto": texto, "ficheiros": list(ficheiros)})


# ----------------------------------------------------------------- livro
ESQ_BRIEF = {"type": "object", "additionalProperties": False,
             "required": ["titulo", "subtitulo", "capa", "temas", "racional"],
             "properties": {
                 "titulo": {"type": "string"}, "subtitulo": {"type": "string"}, "racional": {"type": "string"},
                 "temas": {"type": "array", "items": {"type": "string"}},
                 "capa": {"type": "object", "additionalProperties": False,
                          "required": ["tit1", "tit2", "sub", "costas_tit", "costas_sub", "blurb", "pontos", "lombada", "cena"],
                          "properties": {k: {"type": "string"} for k in
                                         ["tit1", "tit2", "costas_tit", "costas_sub", "blurb", "lombada", "cena"]} |
                          {"sub": {"type": "array", "items": {"type": "string"}},
                           "pontos": {"type": "array", "items": {"type": "string"}}}}}}

ESQ_FICHA = {"type": "object", "additionalProperties": False,
             "required": ["titulo", "subtitulo", "descricao", "keywords", "categorias", "preco_usd", "preco_eur",
                          "declaracao_ia", "notas"],
             "properties": {"titulo": {"type": "string"}, "subtitulo": {"type": "string"},
                            "descricao": {"type": "string"}, "notas": {"type": "string"},
                            "keywords": {"type": "array", "items": {"type": "string"}},
                            "categorias": {"type": "array", "items": {"type": "string"}},
                            "preco_usd": {"type": "number"}, "preco_eur": {"type": "number"},
                            "declaracao_ia": {"type": "string"}}}

COPYRIGHT = ["Copyright {ano} {marca}. All rights reserved.",
             "Tip: place a sheet of paper behind the page you are coloring. Every design is printed on its own page."]


ARQUIVO = H("~/Livros-Prontos")
ESQ_REV = {"type": "object", "additionalProperties": False,
           "required": ["aprovado", "nota", "paginas_refazer", "problemas_gerais", "resumo_pt"],
           "properties": {"aprovado": {"type": "boolean"}, "nota": {"type": "integer"}, "resumo_pt": {"type": "string"},
                          "problemas_gerais": {"type": "array", "items": {"type": "string"}},
                          "paginas_refazer": {"type": "array", "items": {
                              "type": "object", "additionalProperties": False, "required": ["id", "motivo"],
                              "properties": {"id": {"type": "string"}, "motivo": {"type": "string"}}}}}}


def folhas(pasta, L, est, por=12, lado=420):
    """Folhas de contacto com todas as paginas aprovadas, etiquetadas pelo id, para o revisor ver o livro inteiro."""
    from PIL import Image, ImageDraw
    ok = [(p["id"], f"{pasta}/final/{p['id']}.png") for p in L["paginas"] if est.get(p["id"], {}).get("estado") == "aprovada"]
    os.makedirs(f"{pasta}/kit/revisao", exist_ok=True)
    saidas = []
    for i in range(0, len(ok), por):
        lote = ok[i:i + por]
        fol = Image.new("RGB", (4 * (lado + 10) + 10, 3 * (lado + 40) + 10), "white")
        d = ImageDraw.Draw(fol)
        for j, (pid, f) in enumerate(lote):
            im = Image.open(f).convert("RGB"); im.thumbnail((lado, lado))
            x, y = 10 + (j % 4) * (lado + 10), 10 + (j // 4) * (lado + 40)
            d.text((x, y), pid, fill="black"); fol.paste(im, (x, y + 25)); d.rectangle([x, y + 25, x + lado - 1, y + 25 + lado - 1], outline=(180, 180, 180))
        saidas.append(f"{pasta}/kit/revisao/folha-{i // por + 1}.png"); fol.save(saidas[-1])
    return saidas


def verificacoes(pasta, L, est):
    """Checagens que nao precisam de olhos: contas, zona segura, paginas quase iguais."""
    from PIL import Image
    erros = []
    aprov = [p["id"] for p in L["paginas"] if est.get(p["id"], {}).get("estado") == "aprovada"]
    if len(aprov) != len(L["paginas"]):
        erros.append(f"{len(L['paginas']) - len(aprov)} paginas sem aprovacao")
    nums = {int(w) for w in " ".join(L["capa"].get("sub", [])).split() if w.isdigit()}
    if nums and nums != {len(aprov)}:
        erros.append(f"a capa promete {sorted(nums)} desenhos e o livro tem {len(aprov)}")
    if not lj(f"{pasta}/kit/capa.json", {}).get("titulo_dentro_zona_segura"):
        erros.append("titulo da capa fora da zona segura")
    if lj(f"{pasta}/kit/interior.json", {}).get("paginas_interior", 0) < 24:
        erros.append("interior com menos de 24 paginas")
    hs = {}
    for pid in aprov:
        im = Image.open(f"{pasta}/final/{pid}.png").convert("L").resize((9, 8))
        px_ = list(im.getdata())
        hs[pid] = [px_[r * 9 + c] > px_[r * 9 + c + 1] for r in range(8) for c in range(8)]
    parecidas = [f"{a} e {b}" for i, a in enumerate(aprov) for b in aprov[i + 1:]
                 if sum(x != y for x, y in zip(hs[a], hs[b])) <= 6]
    return erros, parecidas


ESQ_CONF = {"type": "object", "additionalProperties": False, "required": ["confirmado", "evidencia"],
            "properties": {"confirmado": {"type": "boolean"}, "evidencia": {"type": "string"}}}


def confirmar(pasta, pid, tema, motivo):
    """Segundo olhar: o defeito apontado na folha de contacto existe mesmo na pagina em tamanho real?
    Calibrado 2026-11-22: na 1a revisao real, 7 de 8 defeitos apontados nao existiam."""
    from PIL import Image
    img = f"{pasta}/kit/revisao/{pid}.png"
    Image.open(f"{pasta}/final/{pid}.png").convert("L").resize((1024, 1024)).save(img)
    d = codex("Verificador", (
        "You check one claimed defect on one page of an adult coloring book. Look only at the attached page.\n"
        f"Page theme: {tema}\nClaimed defect: {motivo}\n"
        "Set confirmado=true only if the defect is clearly and literally visible and would bother a buyer. "
        "Readable letters or digits count as text; hearts, dots, chocolate chips, stripes, a blank music stand or "
        "blank book spines do not. A pose or action of a character or animal that differs from the theme is NOT a "
        "defect. Small style differences of a recurring character between pages are NOT a defect. If you are not sure, confirmado=false. "
        "In evidencia, say in Portuguese exactly where you see it, or why it is not there."),
        ESQ_CONF, pasta, f"{pasta}/kit/revisao/{pid}.conf.json", [img])
    return d


def slug(t):
    return "".join(c if c.isalnum() else "-" for c in t.lower()).strip("-").replace("--", "-")


def custo_livro(pasta):
    est = lj(f"{pasta}/estado.json", {})
    n = sum(len(s.get("tentativas", [])) + len(s.get("historico", [])) for s in est.values())
    return n * CUSTO_IMG + len(glob.glob(f"{pasta}/kit/arte-capa*.png")) * CUSTO_CAPA

# ----------------------------------------------------------------- preco (decisao 0012)
def custo_impressao_kdp(paginas):
    """Amazon.com, tinta preta, trim grande (8.5x8.5). Fonte oficial: kdp.amazon.com/help/topic/G201834340, lida 2026-11-22."""
    return 2.84 if paginas <= 110 else 1.00 + 0.017 * paginas


def liquido(canal, p, paginas=0):
    """O que chega por venda depois da plataforma (e da retencao dos EUA no KDP), antes do IRPF."""
    if canal == "kdp":  # royalty 60% a partir de 9.99, 50% abaixo, menos impressao (G201834340); retencao EUA na fonte
        ret = lj(CONFIG, {}).get("retencao_eua", RETENCAO_EUA)
        return ((0.6 if p >= 9.99 else 0.5) * p - custo_impressao_kdp(paginas)) * (1 - ret)
    return p - (0.10 * p + 0.50) - (0.029 * p + 0.30)  # Gumroad: 10% + 0.50 e cartao 2.9% + 0.30 (help article 66)


def custo_criacao_estimado(n_pag):
    """Custo de criar um livro (imagens, capa, Apify), pago uma vez. Media dos livros ja feitos; sem historico, estima."""
    feitos = [m["gasto_registado_usd"] for m in (lj(f) for f in glob.glob(f"{LIV}/*/kit/metricas.json")) if m]
    return round(max(statistics.mean(feitos) if feitos else 0, n_pag * 1.5 * CUSTO_IMG + CUSTO_CAPA), 2)


def preco_abaixo(canal, mediana, paginas=0, custo_criacao=0.0):
    """Regra 0012: o preco mais alto terminado em .49 ou .99 abaixo da mediana dos concorrentes que vendem, desde que a
    PRIMEIRA venda pague o custo de criacao do livro. O IRPF cai sobre o lucro e o custo de criacao desconta, por isso a
    primeira venda (lucro zero) nao paga IRPF; as seguintes pagam (lucro_depois_irpf). Se nada abaixo da mediana paga o
    custo, devolve ok=False e o preco minimo que paga."""
    cfg = lj(CONFIG, {})
    irpf = cfg.get("irpf_estimado", IRPF_ESTIMADO)
    piso = round(max(cfg.get("piso_liquido", 0), custo_criacao), 2)
    def linha(p):
        liq = liquido(canal, p, paginas)
        return {"preco": p, "fica_por_venda": round(liq, 2), "lucro_depois_irpf": round(liq * (1 - irpf), 2),
                "ok": liq >= piso}
    passos = sorted({round(math.floor(mediana) - k + d, 2) for k in range(12) for d in (0.49, 0.99)}, reverse=True)
    abaixo = [x for x in passos if 0 < x < mediana]
    alts = [linha(x) for x in abaixo[:6]]
    acima = sorted({round(math.floor(mediana) + k + d, 2) for k in range(0, 20) for d in (-0.51, -0.01, 0.49, 0.99)})
    minimo = next((linha(x) for x in acima if x > 0 and linha(x)["ok"]), None)
    return {"canal": canal, "mediana_concorrencia": mediana, "irpf_estimado": irpf, "custo_criacao": piso,
            "paginas": paginas, **(alts[0] if alts else {"preco": None, "ok": False}), "alternativas": alts,
            "preco_minimo_que_paga": minimo}


# ----------------------------------------------------------------- benchmark (decisao 0012)
ESQ_BENCH = {"type": "object", "additionalProperties": False,
             "required": ["usar_personagem", "personagem", "racional_personagem", "estilo_paginas", "direcao_capa",
                          "temas_que_vendem", "queixas", "elogios", "fazer_melhor", "relatorio_md", "confianca"],
             "properties": {"usar_personagem": {"type": "boolean"}, "personagem": {"type": "string"},
                            "racional_personagem": {"type": "string"}, "estilo_paginas": {"type": "string"},
                            "direcao_capa": {"type": "string"}, "relatorio_md": {"type": "string"},
                            "confianca": {"type": "integer"}} |
                           {k: {"type": "array", "items": {"type": "string"}}
                            for k in ["temas_que_vendem", "queixas", "elogios", "fazer_melhor"]}}

# Regras que valem em qualquer nicho (aprendidas no livro 1): o benchmark escolhe o estilo, o codigo junta isto.
REGRAS_PAGINA = ("Draw the whole scene as one complete vignette centered on the page with a wide white margin on every "
                 "side; nothing touches or is cut by the page edges. Avoid hanging signs, labels, posters, book titles and "
                 "anything that could carry writing. Black outlines on a pure white background, no shading, no hatching, "
                 "no gray, no color, no text, no letters, no numbers.")


def licoes():
    return open(LICOES).read()[-3000:] if os.path.exists(LICOES) else "(ainda nao ha licoes)"


def _attr(it, *chaves):
    return next((a.get("value") for a in it.get("attributes") or [] if a.get("key") in chaves), None)


def e_colorir(t):
    t = (t or "").lower()
    if "coloring" not in t and "colouring" not in t:
        return False
    if "kids" in t and "adult" not in t:
        return False
    return not any(w in t for w in ["puzzle", "sticker", "calendar", "planner", "journal", "word search", "activity book"])


def folha_concorrencia(bd, livros):
    """So com autorizacao do board (config benchmark_imagens_amazon): capas e paginas de amostra dos que mais vendem."""
    import urllib.request
    from PIL import Image, ImageDraw
    os.makedirs(f"{bd}/img", exist_ok=True)
    def baixa(url, f):
        if not os.path.exists(f):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            open(f, "wb").write(urllib.request.urlopen(req, timeout=30).read())
        return f
    capas = [(f"{i + 1}", baixa(x["capa"], f"{bd}/img/capa-{i + 1}.jpg")) for i, x in enumerate(livros[:12]) if x.get("capa")]
    inter = [(f"{i + 1}.{j + 1}", baixa(u, f"{bd}/img/int-{i + 1}-{j + 1}.jpg"))
             for i, x in enumerate(livros[:6]) for j, u in enumerate(x.get("galeria", [])[:2])]
    saidas = []
    for nomef, lote in (("capas", capas), ("interiores", inter)):
        if not lote:
            continue
        lado = 400
        fol = Image.new("RGB", (4 * (lado + 10) + 10, ((len(lote) + 3) // 4) * (lado + 40) + 10), "white")
        d = ImageDraw.Draw(fol)
        for j, (rot, f) in enumerate(lote):
            im = Image.open(f).convert("RGB"); im.thumbnail((lado, lado))
            x, y = 10 + (j % 4) * (lado + 10), 10 + (j // 4) * (lado + 40)
            d.text((x, y), rot, fill="black"); fol.paste(im, (x, y + 25))
        saidas.append(f"{bd}/folha-{nomef}.png"); fol.save(saidas[-1])
    return saidas


def benchmark(nome, pasta, ped, n_pag, ap):
    """Passo 0 (decisao 0012): antes do brief, ver o que a concorrencia faz (capas, desenhos, preco) para fazer melhor."""
    bf, bd = f"{pasta}/benchmark.json", f"{pasta}/benchmark"
    if os.path.exists(bf):
        return lj(bf)
    os.makedirs(bd, exist_ok=True)
    fonte = H(ped["dados_mercado"]) if ped.get("dados_mercado") else None
    if not fonte:  # sem recolha recente: chama o actor da Apify (decisao 0008)
        kws = ped.get("keywords") or []
        if not kws:
            raise RuntimeError("pedido sem keywords nem dados_mercado para o benchmark")
        n = int(ped.get("livros_por_kw", 36))
        custo = len(kws) * n * CUSTO_APIFY_LIVRO
        if gasto_mes() + custo > TETO_MES and not ap.get("teto_mes_" + hoje()[:7]):
            portao(nome, "teto_mes_" + hoje()[:7], f"Benchmark custaria ~US$ {custo:.2f}; mes iria acima de US$ {TETO_MES}.")
            return "portao"
        log(nome, "benchmark apify", kws)
        r = run([PY, f"{BIN}/mercado_amazon2.py"] + kws, timeout=2400, extra={"LIVROS_POR_KW": str(n)})
        if r.returncode:
            raise RuntimeError("apify: " + (r.stdout + r.stderr)[-400:])
        info = json.loads(r.stdout.strip().splitlines()[-1])
        gasto(f"{nome}: benchmark apify", info.get("custo_usd") or custo)
        fonte = info["ficheiro"]
    vistos, livros = set(), []
    for it in lj(fonte)["itens"]:
        if it.get("asin") in vistos or not e_colorir(it.get("title")) or not (it.get("price") or {}).get("value"):
            continue
        vistos.add(it.get("asin"))
        data = _attr(it, "Publication date")
        try:
            data = datetime.datetime.strptime(data, "%B %d, %Y").date().isoformat()
        except Exception:
            pass
        livros.append({"titulo": it["title"], "autor": it.get("author"), "preco": it["price"]["value"],
                       "reviews": it.get("reviewsCount") or 0, "estrelas": it.get("stars"),
                       "bsr": next((r["rank"] for r in it.get("bestsellerRanks") or [] if r.get("category") == "Books"), None),
                       "publicado": data, "paginas": _attr(it, "Print length", "Paperback"),
                       "resumo_reviews": (it.get("aiReviewsSummary") or {}).get("text"),
                       "descricao": str(it.get("bookDescription") or it.get("description") or "")[:600],
                       "capa": it.get("thumbnailImage"), "galeria": (it.get("highResolutionImages") or [])[1:4]})
    livros.sort(key=lambda x: x["bsr"] or 10 ** 9)
    vendem = [x for x in livros if x["bsr"] and x["bsr"] < 100000]
    if len(vendem) < 5:
        raise RuntimeError(f"benchmark: so {len(vendem)} livros de colorir com BSR < 100k")
    precos = {"amazon": {"mediana": round(statistics.median(x["preco"] for x in vendem), 2), "n": len(vendem),
                         "fonte": fonte, "nota": "livros de colorir com BSR < 100k na Amazon.com, fotografia de um dia"}}
    if ped.get("gumroad_query"):
        r = run(["gumroad", "products", "comps", "--query", ped["gumroad_query"], "--json"], timeout=120)
        try:
            c = json.loads(r.stdout)["comps"]
            precos["gumroad"] = {"mediana": c["price_cents"]["p50"] / 100, "p25": c["price_cents"]["p25"] / 100,
                                 "p75": c["price_cents"]["p75"] / 100, "n": c["count"], "query": ped["gumroad_query"],
                                 "nota": "comps do Gumroad: todos os produtos pagos que batem na pesquisa (inclui bundles)"}
        except Exception:
            log(nome, "comps gumroad falhou", r.stderr[-200:])
    gj(f"{bd}/dados.json", {"livros": livros[:40], "precos": precos})
    imgs = folha_concorrencia(bd, vendem) if lj(CONFIG, {}).get("benchmark_imagens_amazon") else []
    log(nome, "benchmark analista", len(livros), "livros", len(imgs), "folhas")
    a = codex("Analista", (
        f"Benchmark da concorrencia antes de fazermos um livro de colorir. Pedido do board: {json.dumps(ped, ensure_ascii=False)}.\n"
        "Dados: o ficheiro benchmark/dados.json nesta pasta (livros de colorir da Amazon.com ordenados por BSR: preco, "
        "reviews, estrelas, data de publicacao, paginas, resumo das reviews, descricao). Le-o.\n"
        + ("As imagens anexas sao as capas (numeradas pela ordem do ficheiro) e paginas de amostra (livro.amostra) dos "
           "que mais vendem. Olha para elas. " if imgs else
           "Nao tens imagens: julga capas e desenhos so pelo que titulos, descricoes e reviews dizem, e escreve isso "
           "no relatorio. ")
        + f"Licoes de livros anteriores:\n{licoes()}\n"
        "Responde:\n(1) usar_personagem: os que vendem neste nicho usam uma personagem recorrente (ex.: o mesmo gato em "
        "todas as paginas)? So true se os dados mostram que ajuda aqui. personagem = descricao curta em ingles (vazio se "
        "false). racional_personagem com a evidencia.\n(2) estilo_paginas: prompt em ingles para gerar cada pagina, com "
        "{tema} onde entra o tema; diz o nivel de detalhe e o traco que este nicho pede (bold and easy, detalhado, etc.) "
        "e a personagem se usar_personagem. Sem regras de margem, texto ou cor: o codigo junta-as.\n(3) direcao_capa: em "
        "ingles, como a ilustracao a cores da nossa capa se destaca das capas que vendem.\n(4) temas_que_vendem; queixas e "
        "elogios que se repetem nas reviews; fazer_melhor = o que fazemos para bater os melhores.\n"
        "Nao decides o preco (o codigo calcula). Separa factos medidos de estimativas. Nunca inventes numeros. "
        "relatorio_md em portugues, curto, com tabela dos 10 que mais vendem. confianca 0-100."),
        ESQ_BENCH, pasta, f"{bd}/analise.json", imgs)
    if "{tema}" not in a["estilo_paginas"]:
        raise RuntimeError("benchmark: estilo_paginas sem {tema}")
    b = dict(a, precos=precos, imagens=bool(imgs), data=hoje())
    gj(bf, b)
    est_pag = 2 * n_pag + 2
    linhas = [f"# Benchmark: {ped.get('nicho', '')[:80]}", "", f"{hoje()}. Confianca {a['confianca']}%. "
              f"Imagens dos concorrentes vistas: {'sim' if imgs else 'nao (so texto)'}.", "",
              "## Preco (regra 0012: abaixo da mediana, com piso depois de comissao e reserva de imposto)",
              "", "| Canal | Mediana concorrencia | Nosso preco | Fica por venda | Lucro por venda depois do IRPF (2a venda em diante) | 1a venda paga a criacao | Preco minimo que paga |", "|---|---|---|---|---|---|---|"]
    for canal, k in (("kdp", "amazon"), ("gumroad", "gumroad")):
        if k in precos:
            pr = preco_abaixo(canal, precos[k]["mediana"], est_pag if canal == "kdp" else 0, custo_criacao_estimado(n_pag))
            linhas += [f"| {canal} | {pr['mediana_concorrencia']} ({precos[k]['n']} produtos) | {pr['preco']} | "
                       f"{pr['fica_por_venda']} | {pr['lucro_depois_irpf']} | {'sim' if pr['ok'] else 'NAO'} (US$ {pr['custo_criacao']}) | "
                       f"{(pr['preco_minimo_que_paga'] or {}).get('preco', '-')} |"]
    linhas += ["", f"IRPF estimado {int(lj(CONFIG, {}).get('irpf_estimado', IRPF_ESTIMADO) * 100)}% sobre o lucro e retencao EUA "
               "5% no KDP: NAO VERIFICADO, confirmar com gestor. KDP estimado com ~" + str(est_pag) + " paginas; o preco final sai na ficha.",
               "", "## Personagem", f"{'Sim: ' + a['personagem'] if a['usar_personagem'] else 'Nao.'} {a['racional_personagem']}",
               "", "## Fazer melhor"] + [f"- {x}" for x in a["fazer_melhor"]] + \
             ["", "## Capa", a["direcao_capa"], "", "## Estilo das paginas", a["estilo_paginas"], "", a["relatorio_md"]]
    open(f"{pasta}/BENCHMARK.md", "w").write("\n".join(linhas) + "\n")
    return b


# ----------------------------------------------------------------- retro (decisao 0012)
ESQ_RETRO = {"type": "object", "additionalProperties": False,
             "required": ["correu_bem", "correu_mal", "parar", "melhorar", "licoes", "resumo_pt"],
             "properties": {"resumo_pt": {"type": "string"},
                            "melhorar": {"type": "array", "items": {
                                "type": "object", "additionalProperties": False,
                                "required": ["acao", "evidencia", "ganho_esperado", "tipo"],
                                "properties": {"acao": {"type": "string"}, "evidencia": {"type": "string"},
                                               "ganho_esperado": {"type": "string"},
                                               "tipo": {"type": "string", "enum": ["custo", "qualidade", "tempo"]}}}}} |
                           {k: {"type": "array", "items": {"type": "string"}}
                            for k in ["correu_bem", "correu_mal", "parar", "licoes"]}}


def metricas(pasta, L, est, rv):
    from collections import Counter
    pags = [est.get(p["id"], {}) for p in L["paginas"]]
    tent = [tt for s in pags for tt in s.get("historico", []) + s.get("tentativas", [])]
    aprov = sum(1 for s in pags if s.get("estado") == "aprovada")
    primeira = sum(1 for s in pags if s.get("estado") == "aprovada" and len(s.get("tentativas", [])) == 1
                   and not s.get("historico"))
    motivos = Counter()
    for tt in tent:
        r = tt.get("revisor") or {}
        if not r.get("aprovada"):
            for m in (r.get("defeitos") or []) + (r.get("problemas") or []):
                motivos[str(m)[:140]] += 1
    base = os.path.basename(pasta)
    gastos = [json.loads(l) for l in open(GASTOS)] if os.path.exists(GASTOS) else []
    gasto_reg = round(sum(g["usd"] for g in gastos if base in g["desc"]), 2)
    return {"livro": L.get("titulo"), "paginas": len(pags), "aprovadas": aprov, "imagens_geradas": len(tent),
            "imagens_por_pagina": round(len(tent) / max(aprov, 1), 2),
            "aprovadas_a_primeira_pct": round(100 * primeira / max(len(pags), 1)),
            "chumbos_por_motivo_top10": motivos.most_common(10),
            "refeitas_pela_revisao_final": sum(1 for s in pags if s.get("correcoes_revisao")),
            "revisao_final": {"nota": rv.get("nota"), "apontadas": len(rv.get("apontadas", [])),
                              "confirmadas": len(rv.get("paginas_refazer", [])), "descartadas": len(rv.get("descartadas", []))},
            "gasto_registado_usd": gasto_reg, "custo_imagens_estimado_usd": round(custo_livro(pasta), 2),
            "custo_por_pagina_aprovada_usd": round(gasto_reg / max(aprov, 1), 3),
            "nota_custos": "codex (subscricao) custa 0 por chamada; so imagens e Apify entram no gasto",
            "teve_benchmark": os.path.exists(f"{pasta}/benchmark.json")}


DRIVE_PASTA_LIVROS = (lj(CONFIG, {}) or {}).get("drive_pasta_livros", "")  # Drive pessoal: pasta dos livros (config.json)
RCLONE = H("~/.local/bin/rclone")


def drive_e_planilha(nome, pasta, L, dest):
    """Passo K (pedido do Cleiton, 22 Nov 2026): sobe o livro inteiro (PDF para imprimir), a amostra de 5 paginas e os
    ficheiros KDP para o Drive pessoal e reconstroi a aba Livros da planilha. Nao trava o livro: se falhar (ex.: login
    semanal do Drive expirado), tenta de novo na proxima volta."""
    import subprocess
    kit = f"{pasta}/kit"
    py = sys.executable
    if not os.path.exists(f"{kit}/imprimivel.pdf"):
        subprocess.run([py, f"{BIN}/imprimivel.py", pasta], check=True, capture_output=True)
    if not os.path.exists(f"{kit}/amostra/amostra.pdf"):
        subprocess.run([py, f"{BIN}/imprimivel.py", pasta, "--amostra", "5"], check=True, capture_output=True)
    fic = lj(f"{kit}/ficha.json", {})
    if not os.path.exists(f"{kit}/precos.json"):
        pk, pg = fic.get("preco_kdp") or {}, fic.get("preco_gumroad") or {}
        gj(f"{kit}/precos.json", {
            "kdp": {"mediana": pk.get("mediana_concorrencia"), "fonte": "benchmark do livro (BENCHMARK.md)",
                    "preco": pk.get("preco", fic.get("preco_usd")), "estado": "proposta (upload pendente)"},
            "gumroad": {"mediana": pg.get("mediana_concorrencia"), "fonte": "benchmark do livro (BENCHMARK.md)",
                        "preco": pg.get("preco"), "estado": "proposta (rascunho)"}})
    dr = lj(f"{kit}/drive.json", {}) or {}
    if not dr.get("pasta"):
        raiz = ["--drive-root-folder-id", DRIVE_PASTA_LIVROS]
        r = subprocess.run([RCLONE, "lsf", "pessoal:", "--dirs-only"] + raiz, capture_output=True, text=True, timeout=120)
        if r.returncode:
            raise RuntimeError("rclone sem acesso ao Drive (login semanal?): " + r.stderr[-200:])
        nums = [int(x[:2]) for x in r.stdout.splitlines() if x[:2].isdigit() and x[2:3] == " "]
        t = fic.get("titulo") or L.get("titulo") or nome
        d = f"pessoal:{(max(nums) + 1 if nums else 1):02d} {t}"
        envios = [(f"{kit}/imprimivel.pdf", f"{d}/{t} - Full Book (printable, US Letter).pdf"),
                  (f"{kit}/amostra/amostra.pdf", f"{d}/{t} - Free Sample (5 pages).pdf"),
                  (f"{kit}/interior.pdf", f"{d}/KDP files/{t} - KDP Interior.pdf"),
                  (f"{kit}/capa.pdf", f"{d}/KDP files/{t} - KDP Cover.pdf")]
        for a, b in envios:
            subprocess.run([RCLONE, "copyto", a, b] + raiz, check=True, capture_output=True, timeout=900)
        js = json.loads(subprocess.run([RCLONE, "lsjson", d, "-R"] + raiz, check=True, capture_output=True, text=True).stdout)
        pid = json.loads(subprocess.run([RCLONE, "lsjson", "pessoal:", "--dirs-only"] + raiz, check=True,
                                        capture_output=True, text=True).stdout)
        dr = {"pasta": next(x["ID"] for x in pid if x["Name"] == d.split(":", 1)[1]),
              "amostra": next((x["ID"] for x in js if "Free Sample" in x["Name"]), ""),
              "estado": "Kit pronto: upload KDP pendente (Cleiton)"}
        gj(f"{kit}/drive.json", dr)
        log(nome, "drive", d)
    subprocess.run([py, f"{BIN}/planilha.py"], check=True, capture_output=True, timeout=300)
    log(nome, "planilha", "aba Livros atualizada")


def retro(nome, pasta, L, est, rv):
    """Sprint review no fim de cada livro (decisao 0012): correu bem, correu mal, parar, melhorar.
    Mudancas ao codigo ficam so propostas em ~/empresa/melhorias.md; o board aprova."""
    m = metricas(pasta, L, est, rv)
    gj(f"{pasta}/kit/metricas.json", m)
    antes = [{"livro": x.get("livro"), **{k: x.get(k) for k in ("imagens_por_pagina", "aprovadas_a_primeira_pct",
             "custo_por_pagina_aprovada_usd", "gasto_registado_usd")}}
             for x in (lj(f) for f in glob.glob(f"{LIV}/*/kit/metricas.json") if not f.startswith(pasta)) if x]
    log(nome, "retro")
    r = codex("Retro", (
        "Fazes o sprint review da nossa linha de montagem de livros de colorir, depois de acabar este livro. Objectivo: "
        "gastar o menos possivel para entregar o melhor livro.\n"
        f"Metricas medidas pelo codigo: {json.dumps(m, ensure_ascii=False)}\n"
        f"Livros anteriores (para comparar): {json.dumps(antes, ensure_ascii=False) if antes else 'nenhum'}\n"
        "Le tambem kit/REVISAO.md e, se existir, BENCHMARK.md nesta pasta. Licoes que ja tinhamos:\n" + licoes() + "\n"
        "Responde em portugues: correu_bem, correu_mal, parar (o que deixamos de fazer), melhorar (accoes concretas; cada "
        "uma com a metrica que a justifica, o ganho esperado em US$ ou em qualidade, e o tipo), licoes (regras curtas para "
        "os proximos benchmarks e briefs, so as novas) e resumo_pt (3-5 frases). Usa so os numeros dados; nunca inventes. "
        "Mudancas ao codigo sao propostas: o board aprova."), ESQ_RETRO, pasta, f"{pasta}/kit/retro.json")
    md = [f"# Sprint review: {L['titulo']}", "", f"{hoje()}.", "", r["resumo_pt"], "", "## Numeros",
          f"- Paginas aprovadas: {m['aprovadas']}/{m['paginas']}; a primeira: {m['aprovadas_a_primeira_pct']}%",
          f"- Imagens geradas: {m['imagens_geradas']} ({m['imagens_por_pagina']} por pagina)",
          f"- Gasto registado: US$ {m['gasto_registado_usd']} (US$ {m['custo_por_pagina_aprovada_usd']} por pagina)",
          f"- Revisao final: nota {m['revisao_final']['nota']}, {m['revisao_final']['apontadas']} apontadas, "
          f"{m['revisao_final']['confirmadas']} confirmadas"]
    for tit, k in (("Correu bem", "correu_bem"), ("Correu mal", "correu_mal"), ("Parar", "parar"), ("Licoes", "licoes")):
        md += ["", f"## {tit}"] + [f"- {x}" for x in r[k]]
    md += ["", "## Melhorar"] + [f"- [{x['tipo']}] {x['acao']} (ganho: {x['ganho_esperado']}; porque: {x['evidencia']})"
                                 for x in r["melhorar"]]
    open(f"{pasta}/kit/RETRO.md", "w").write("\n".join(md) + "\n")
    with open(MELHORIAS, "a") as f:
        f.write(f"\n## {hoje()} {L['titulo']} (propostas, board aprova)\n" +
                "".join(f"- [ ] [{x['tipo']}] {x['acao']} (ganho: {x['ganho_esperado']})\n" for x in r["melhorar"]))
    with open(LICOES, "a") as f:
        f.write(f"\n## {L['titulo']} ({hoje()})\n" + "".join(f"- {x}\n" for x in r["licoes"]))
    return r


def livro(t, nome):
    pasta = H(t["pasta"])
    L = lj(f"{pasta}/livro.json")
    ap = lj(f"{pasta}/aprovacoes.json", {})
    os.makedirs(f"{pasta}/kit", exist_ok=True)
    ped = L.get("pedido", {})
    n_pag = int(ped.get("paginas", 50))

    # 0. benchmark da concorrencia (decisao 0012)
    if not L.get("paginas"):
        bench = benchmark(nome, pasta, ped, n_pag, ap)
        if bench == "portao":
            return "portao"

    # A. brief
    if not L.get("paginas"):
        log(nome, "brief")
        b = codex("Editor", (
            f"Prepara o brief de um livro de colorir para adultos. Pedido do board: {json.dumps(ped, ensure_ascii=False)}.\n"
            f"Da: titulo e subtitulo (lingua do mercado), {n_pag} temas de pagina DIFERENTES entre si (cada tema uma cena "
            "concreta e desenhavel em linhas grossas, sem texto, sem marcas nem personagens de terceiros), os textos da capa "
            "(tit1 = palavra grande do titulo, tit2 = resto do nome do livro, no maximo 3 palavras e 20 caracteres, sem as palavras Coloring Book for Adults, sub = 2 linhas curtas em maiusculas, textos da "
            "contracapa sem promessas de saude, 3 pontos curtos, lombada = titulo em maiusculas, cena = descricao da "
            "ilustracao a cores da capa) e um racional curto em portugues. O numero de desenhos tem de bater certo com "
            f"{n_pag}. Formato 8.5x8.5 pol, paginas so de um lado.\n"
            f"Segue o benchmark da concorrencia (BENCHMARK.md nesta pasta). Personagem recorrente: "
            f"{bench['personagem'] if bench['usar_personagem'] else 'NENHUMA, nao ponhas personagem fixa'}. "
            f"Temas que vendem: {'; '.join(bench['temas_que_vendem'])}. Fazer melhor: {'; '.join(bench['fazer_melhor'])}. "
            f"Capa: {bench['direcao_capa']}\nLicoes de livros anteriores:\n{licoes()}"), ESQ_BRIEF, pasta, f"{pasta}/brief.json")
        if len(b["temas"]) < n_pag:
            raise RuntimeError(f"brief com {len(b['temas'])} temas, pedido {n_pag}")
        L.update(titulo=b["titulo"], subtitulo=b["subtitulo"], capa=b["capa"], tamanho="1024x1024",
                 estilo=L["estilo"] if L.get("estilo_fixo") else bench["estilo_paginas"] + " " + REGRAS_PAGINA,
                 mascote=bench["personagem"] if bench["usar_personagem"] else None, capa_direcao=bench["direcao_capa"],
                 paginas=[{"id": f"p{i + 1:02d}", "tema": x} for i, x in enumerate(b["temas"][:n_pag])])
        gj(f"{pasta}/livro.json", L)
    if not ap.get("brief") or not L.get("marca") or "[" in L.get("marca", "["):
        portao(nome, "brief", f"Aprovar brief: \"{L['titulo']}\" ({len(L['paginas'])} paginas). "
               f"Marca/autor: {L.get('marca') or 'FALTA DEFINIR'}.",
               [f"{pasta}/BENCHMARK.md", f"{pasta}/livro.json", f"{pasta}/brief.json"])
        return "portao"

    # C. paginas
    est = lj(f"{pasta}/estado.json", {})
    feitas = [p for p in L["paginas"] if est.get(p["id"], {}).get("estado") in ("aprovada", "fila_humana")]
    if len(feitas) < len(L["paginas"]):
        falta = (len(L["paginas"]) - len(feitas)) * 1.5 * CUSTO_IMG
        if custo_livro(pasta) + falta > TETO_LIVRO and not ap.get("teto_livro"):
            portao(nome, "teto_livro", f"Paginas custariam ~US$ {custo_livro(pasta) + falta:.2f} (> teto US$ {TETO_LIVRO}).")
            return "portao"
        if gasto_mes() + falta > TETO_MES and not ap.get("teto_mes_" + hoje()[:7]):
            portao(nome, "teto_mes_" + hoje()[:7], f"Gasto do mes iria a ~US$ {gasto_mes() + falta:.2f} (> teto US$ {TETO_MES}).")
            return "portao"
        log(nome, "paginas", len(feitas), "/", len(L["paginas"]))
        antes = custo_livro(pasta)
        r = run([PY, f"{BIN}/linha.py", pasta], timeout=6 * 3600)
        open(f"{pasta}/execucao.log", "a").write(r.stdout + r.stderr)
        gasto(f"{nome}: paginas", custo_livro(pasta) - antes)
        est = lj(f"{pasta}/estado.json", {})
    falhadas = [k for k, s in est.items() if s.get("estado") == "fila_humana"]
    if falhadas and not ap.get("paginas_falhadas"):
        portao(nome, "paginas_falhadas", f"{len(falhadas)} paginas falharam 3 vezes ({', '.join(falhadas)}). "
               "Opcoes: refazer com tema novo, ou seguir sem elas (o numero de desenhos na capa muda).",
               [f"{pasta}/tentativas"])
        return "portao"

    # D. interior
    if not os.path.exists(f"{pasta}/kit/interior.pdf") or os.path.getmtime(f"{pasta}/kit/interior.pdf") < os.path.getmtime(f"{pasta}/estado.json"):
        log(nome, "interior")
        L.setdefault("copyright", [c.format(ano=datetime.date.today().year, marca=L["marca"]) for c in COPYRIGHT])
        gj(f"{pasta}/livro.json", L)
        r = run([PY, f"{BIN}/montar.py", "interior", pasta])
        if r.returncode:
            raise RuntimeError("interior: " + r.stderr[-400:])
    n_int = lj(f"{pasta}/kit/interior.json")["paginas_interior"]
    if n_int < 24 and not ped.get("teste"):
        raise RuntimeError(f"interior com {n_int} paginas (KDP minimo 24)")

    # E. capa
    arte = f"{pasta}/kit/arte-capa.png"
    if not os.path.exists(arte):
        log(nome, "arte da capa")
        prompt = ("Warm, cozy hand-drawn illustration in soft muted colors with brown ink outlines, storybook style: "
                  + L["capa"]["cena"] + ". Centered vignette, no frame, no text, no letters, plain solid cream "
                  "background color #FDF0DB around the scene, generous empty margin on every side."
                  + (" Art direction: " + L["capa_direcao"] if L.get("capa_direcao") else ""))
        r = run([PY, f"{BIN}/gerar_imagem.py", "gpt-image-2", "low", arte, prompt], extra={"TAMANHO": "1024x1024"})
        if r.returncode:
            raise RuntimeError("arte capa: " + r.stdout[-300:])
        gasto(f"{nome}: arte capa", CUSTO_CAPA)
    if not os.path.exists(f"{pasta}/kit/capa.pdf") or os.path.getmtime(f"{pasta}/kit/capa.pdf") < os.path.getmtime(f"{pasta}/kit/interior.pdf"):
        log(nome, "capa")
        aprov = [est[p["id"]]["tentativas"][-1]["ficheiro"] for p in L["paginas"]
                 if est.get(p["id"], {}).get("estado") == "aprovada"]
        r = run([PY, f"{BIN}/capa_final.py", f"{LIV}/fontes", arte, str(n_int), f"{pasta}/kit/capa"] + aprov[:4],
                extra={"LIVRO_JSON": f"{pasta}/livro.json"})
        if r.returncode:
            raise RuntimeError("capa: " + r.stderr[-400:])
        info = json.loads(r.stdout.strip().splitlines()[-1])
        if not info["titulo_dentro_zona_segura"]:
            raise RuntimeError("titulo da capa fora da zona segura")
        gj(f"{pasta}/kit/capa.json", info)

    # F. ficha
    if not os.path.exists(f"{pasta}/kit/ficha.json"):
        log(nome, "ficha")
        n_des = sum(1 for s in est.values() if s.get("estado") == "aprovada")
        f = codex("Editor", (
            f"Prepara a ficha KDP (paperback) deste livro: titulo \"{L['titulo']}\", subtitulo \"{L['subtitulo']}\", "
            f"{n_des} desenhos, 8.5x8.5 pol, paginas so de um lado, {n_int} paginas, temas: "
            f"{'; '.join(p['tema'] for p in L['paginas'][:12])}... Mercado: {ped.get('mercado', 'Amazon.com')}.\n"
            "Da: titulo, subtitulo, descricao (honesta, sem promessas de saude, menciona paginas so de um lado), "
            "exactamente 7 keywords (sem marcas nem autores de terceiros, sem repetir palavras do titulo), 2 categorias "
            "sugeridas, preco_usd e preco_eur (o codigo substitui o USD pela regra de preco 0012), declaracao_ia (o que declarar: interior e "
            "capa gerados por IA, ferramenta OpenAI gpt-image-2, com edicao humana), notas em portugues."),
            ESQ_FICHA, pasta, f"{pasta}/kit/ficha.json")
        if len(f["keywords"]) != 7:
            raise RuntimeError(f"ficha com {len(f['keywords'])} keywords")
        bench = lj(f"{pasta}/benchmark.json")
        if bench:
            base = os.path.basename(pasta)
            gasto_livro = sum(json.loads(l)["usd"] for l in open(GASTOS) if base in json.loads(l)["desc"])
            cc = round(max(gasto_livro, custo_livro(pasta)), 2)
            pk = preco_abaixo("kdp", bench["precos"]["amazon"]["mediana"], n_int, cc)
            f.update(preco_usd=pk["preco"], preco_kdp=pk)
            if "gumroad" in bench["precos"]:
                f["preco_gumroad"] = preco_abaixo("gumroad", bench["precos"]["gumroad"]["mediana"], 0, cc)
            gj(f"{pasta}/kit/ficha.json", f)
    fic = lj(f"{pasta}/kit/ficha.json")
    if any(not fic.get(k, {"ok": True})["ok"] for k in ("preco_kdp", "preco_gumroad")) and not ap.get("preco"):
        portao(nome, "preco", "Nenhum preco abaixo da concorrencia deixa na 1a venda o custo de criacao do livro. "
               "Ver preco_minimo_que_paga em kit/ficha.json.",
               [f"{pasta}/kit/ficha.json", f"{pasta}/BENCHMARK.md"])
        return "portao"

    # G. revisao do livro inteiro (agente Revisor com todas as paginas, capa e ficha)
    rev_f = f"{pasta}/kit/revisao.json"
    if not os.path.exists(rev_f) or os.path.getmtime(rev_f) < os.path.getmtime(f"{pasta}/kit/capa.pdf"):
        log(nome, "revisao final")
        erros, parecidas = verificacoes(pasta, L, est)
        fic = lj(f"{pasta}/kit/ficha.json")
        imgs = folhas(pasta, L, est) + [f"{pasta}/kit/capa-preview.png"]
        temas = "\n".join(f"{p['id']}: {p['tema']}" for p in L["paginas"])
        masc = L.get("mascote", "Toffee, a small chubby tabby cat" if "Toffee" in L.get("estilo", "") else None)
        masc_txt = f"Mascot: {masc}, should appear once on every page.\n" if masc else "No recurring mascot.\n"
        rv = codex("Revisor", (
            "You are the final quality reviewer of a complete adult coloring book before it goes to Amazon KDP. "
            "The attached contact sheets show every interior page, labelled with its id; the last image is the full cover "
            f"(back, spine, front). Title: {L['titulo']}. Subtitle: {L['subtitulo']}. Brand: {L['marca']}. "
            + masc_txt + f"Page themes:\n{temas}\n"
            f"Listing description: {fic['descricao']}\nAutomatic checks found: {erros or 'nothing'}. "
            f"Near-identical page pairs by image hash: {parecidas or 'none'}.\n"
            f"FACTS (already verified by code, do not question them): the interior PDF has {n_int} pages; every drawing is "
            "printed on its own page with a blank back, so 'single-sided' is true; the cover title is inside the safe zone; "
            "every page already passed a per-page reviewer for text, gray shading, borders, cut-offs and deformities.\n"
            "Check the BOOK AS A WHOLE: readable text, letters or digits inside drawings; drawings cut off by the page edge; "
            + ("clearly deformed characters or objects; the mascot missing or twice on a page; " if masc else
               "clearly deformed animals, people or objects; ") + "pages that look like copies of each other; "
            "a page whose scene is clearly a different place than its theme; anything resembling a brand or copyrighted "
            "character; cover promises the interior does not keep; description claims that are false or promise health benefits.\n"
            "NOT defects (never list these): small extra details that fit the scene; a person in the scene; "
            + ("the mascot in a different pose or action than the theme says; small style differences of the mascot "
               "between pages; " if masc else "") + "hearts, dots, "
            "stripes, chocolate chips or blank shapes that are not readable letters; a full-color cover over black-and-white "
            "pages; anything you cannot see clearly at contact-sheet size.\n"
            "Only report what you can literally see. If you are not sure, it is not a defect. The pages are small on the "
            "sheets, so each page you list will be re-checked at full size by a second reviewer: list few, concrete defects "
            "with where they are in the drawing. Put in problemas_gerais only real, verifiable problems with the cover or "
            "description, not doubts. Approve the book (aprovado=true) if no page needs redoing and there is no general problem. "
            "Score the whole book from 0 to 100 (100 = ready to sell). Write resumo_pt in Portuguese, 3-6 short sentences."),
            ESQ_REV, pasta, rev_f, imgs)
        # segundo olhar em tamanho real: so ficam os defeitos confirmados
        tema_de = {p["id"]: p["tema"] for p in L["paginas"]}
        confirmadas, descartadas = [], []
        for x in rv["paginas_refazer"]:
            if x["id"] not in tema_de:
                continue
            c = confirmar(pasta, x["id"], tema_de[x["id"]], x["motivo"])
            (confirmadas if c["confirmado"] else descartadas).append(dict(x, evidencia=c["evidencia"]))
        rv.update(apontadas=rv["paginas_refazer"], paginas_refazer=confirmadas, descartadas=descartadas,
                  aprovado=not confirmadas and not rv["problemas_gerais"], verificacoes=erros, parecidas=parecidas, data=hoje())
        gj(rev_f, rv)
        md = [f"# Revisao final: {L['titulo']}", "", f"{hoje()}. Nota {rv['nota']}/100. Aprovado: {'sim' if rv['aprovado'] else 'nao'}.",
              "", rv["resumo_pt"], "", "## Paginas a refazer (confirmadas em tamanho real)"] + \
             [f"- {x['id']}: {x['motivo']} ({x['evidencia']})" for x in confirmadas] + \
             ["", "## Apontadas mas descartadas no segundo olhar"] + [f"- {x['id']}: {x['motivo']} ({x['evidencia']})" for x in descartadas] + \
             ["", "## Problemas gerais"] + [f"- {x}" for x in rv["problemas_gerais"] + erros] + \
             ["", "## Paginas parecidas (hash)"] + [f"- {x}" for x in parecidas]
        open(f"{pasta}/kit/REVISAO.md", "w").write("\n".join(md) + "\n")
    rv = lj(rev_f)
    ids = {p["id"] for p in L["paginas"]}
    refazer = [x for x in rv["paginas_refazer"] if x["id"] in ids]
    if refazer and L.get("revisao_rodadas", 0) < 1:
        log(nome, "revisor manda refazer", [x["id"] for x in refazer])
        for x in refazer:
            velho = est.get(x["id"], {})
            est[x["id"]] = {"estado": "pendente", "tentativas": [], "correcoes_revisao": [x["motivo"]],
                            "historico": velho.get("historico", []) + velho.get("tentativas", [])}
        gj(f"{pasta}/estado.json", est)
        L["revisao_rodadas"] = L.get("revisao_rodadas", 0) + 1
        gj(f"{pasta}/livro.json", L)
        return livro(t, nome)
    if (not rv["aprovado"] or rv.get("verificacoes")) and not ap.get("revisao_final"):
        portao(nome, "revisao_final", f"O revisor do livro inteiro nao aprovou (nota {rv['nota']}/100). Ver o relatorio.",
               [f"{pasta}/kit/REVISAO.md"] + glob.glob(f"{pasta}/kit/revisao/folha-*.png"))
        return "portao"

    # H. arquivo: copia o livro pronto para ~/Livros-Prontos/<titulo>/
    dest = f"{ARQUIVO}/{slug(L['titulo'])}"
    fontes = {"interior.pdf": f"{pasta}/kit/interior.pdf", "capa.pdf": f"{pasta}/kit/capa.pdf",
              "capa-preview.png": f"{pasta}/kit/capa-preview.png", "ficha.json": f"{pasta}/kit/ficha.json",
              "REVISAO.md": f"{pasta}/kit/REVISAO.md"}
    if any(not os.path.exists(f"{dest}/{k}") or os.path.getmtime(f"{dest}/{k}") < os.path.getmtime(v) for k, v in fontes.items()):
        log(nome, "arquivo", dest)
        os.makedirs(dest, exist_ok=True)
        for k, v in fontes.items():
            shutil.copy2(v, f"{dest}/{k}")
        L["arquivo"] = dest
        gj(f"{pasta}/livro.json", L)

    # I. kit
    fic = lj(f"{pasta}/kit/ficha.json")
    md = [f"# Kit de upload: {fic['titulo']}", "", f"Gerado {hoje()}. Upload so pelo Cleiton (decisao 0009).", "",
          "## Ficheiros", "- Interior: kit/interior.pdf", "- Capa: kit/capa.pdf (ver kit/capa-preview.png)", "",
          "## Campos do formulario KDP (pela ordem)", f"- Titulo: {fic['titulo']}", f"- Subtitulo: {fic['subtitulo']}",
          f"- Autor / marca: {L['marca']}", f"- Descricao:\n\n{fic['descricao']}\n",
          "- Keywords:\n" + "\n".join(f"  {i + 1}. {k}" for i, k in enumerate(fic["keywords"])),
          "- Categorias: " + "; ".join(fic["categorias"]), "- Low-content: NAO marcar", "- ISBN: ISBN gratis do KDP",
          f"- Conteudo gerado por IA: SIM. {fic['declaracao_ia']}",
          "- Interior: preto e branco, papel branco, 8.5 x 8.5 pol, sem bleed, capa brilhante ou mate (board)",
          f"- Preco: US$ {fic['preco_usd']} / EUR {fic['preco_eur']} (EUR sem benchmark: NAO VERIFICADO)"] + \
         ([f"- Regra 0012 KDP: mediana dos concorrentes US$ {fic['preco_kdp']['mediana_concorrencia']}, liquido US$ "
           f"{fic['preco_kdp']['fica_por_venda']}/venda, US$ {fic['preco_kdp']['lucro_depois_irpf']} de lucro depois do IRPF"]
          if fic.get("preco_kdp") else []) + \
         ([f"- Gumroad: US$ {fic['preco_gumroad']['preco']} (mediana US$ {fic['preco_gumroad']['mediana_concorrencia']}, "
           f"fica US$ {fic['preco_gumroad']['fica_por_venda']}/venda)"] if fic.get("preco_gumroad") else []) + ["", "## Notas do Editor", fic["notas"], "",
          f"Custo estimado do livro: US$ {custo_livro(pasta):.2f}", "",
          f"Revisao final: nota {rv['nota']}/100 (kit/REVISAO.md). Copia guardada em {dest}."]
    open(f"{pasta}/kit/KIT.md", "w").write("\n".join(md))
    shutil.copy2(f"{pasta}/kit/KIT.md", f"{dest}/KIT.md")

    # J. sprint review (decisao 0012): nao trava o upload
    if not os.path.exists(f"{pasta}/kit/RETRO.md"):
        retro(nome, pasta, L, est, rv)
        shutil.copy2(f"{pasta}/kit/RETRO.md", f"{dest}/RETRO.md")
    # K. Drive pessoal + planilha: nao trava o upload; repete na proxima volta se falhar
    try:
        drive_e_planilha(nome, pasta, L, dest)
    except Exception as e:
        log(nome, "drive", f"falhou, tento na proxima volta: {str(e)[:300]}")
    if not ap.get("upload"):
        portao(nome, "upload", f"Kit pronto: rever capa e interior e fazer o upload no KDP. Diz-me quando estiver feito.",
               [f"{dest}/KIT.md", f"{dest}/RETRO.md", f"{dest}/capa-preview.png", f"{dest}/interior.pdf"])
        return "portao"
    return "feito"


# ----------------------------------------------------------------- pesquisa
ESQ_PESQ = {"type": "object", "additionalProperties": False,
            "required": ["veredicto", "confianca", "relatorio_md"],
            "properties": {"veredicto": {"type": "string", "enum": ["entrar", "testar", "nao_entrar"]},
                           "confianca": {"type": "integer"}, "relatorio_md": {"type": "string"}}}

CAMPOS = ["title", "author", "price", "listPrice", "stars", "reviewsCount", "bestsellerRanks", "monthlyPurchaseVolume",
          "productOverview", "aiReviewsSummary", "url", "input"]


def pesquisa(t, nome):
    pasta = f"{EMP}/projetos/pesquisas/{t['id']}"
    os.makedirs(pasta, exist_ok=True)
    ap = lj(f"{pasta}/aprovacoes.json", {})
    dados = f"{pasta}/dados.json"
    if not os.path.exists(dados):
        n = int(t.get("livros_por_kw", 12))
        custo = len(t["keywords"]) * n * CUSTO_APIFY_LIVRO
        if gasto_mes() + custo > TETO_MES and not ap.get("teto_mes_" + hoje()[:7]):
            portao(nome, "teto_mes_" + hoje()[:7], f"Pesquisa custaria ~US$ {custo:.2f}; mes iria acima de US$ {TETO_MES}.")
            return "portao"
        log(nome, "apify", len(t["keywords"]), "keywords")
        r = run([PY, f"{BIN}/mercado_amazon2.py"] + t["keywords"], timeout=2400, extra={"LIVROS_POR_KW": str(n)})
        if r.returncode:
            raise RuntimeError("apify: " + (r.stdout + r.stderr)[-400:])
        info = json.loads(r.stdout.strip().splitlines()[-1])
        gasto(f"{nome}: apify", info.get("custo_usd") or custo)
        bruto = lj(info["ficheiro"])
        enxuto = [{k: (it.get(k) if k != "aiReviewsSummary" else (it.get(k) or {}).get("text")) for k in CAMPOS}
                  for it in bruto["itens"]]
        gj(dados, {"keywords": t["keywords"], "fonte": info["ficheiro"], "itens": enxuto})
    if not os.path.exists(f"{pasta}/analise.json"):
        log(nome, "analista")
        a = codex("Analista", (
            f"Pergunta do board: {t['pergunta']}\nDados: o ficheiro dados.json nesta pasta (livros da Amazon.com recolhidos "
            "pelo Apify: preco, estrelas, numero de avaliacoes, BSR, compras/mes, resumo das avaliacoes). Le-o.\n"
            "Avalia a oportunidade: procura (BSR, compras/mes), concorrencia (quantos com muitas avaliacoes, idade), "
            "precos (paperback vs capa dura), queixas e elogios recorrentes, riscos (promessas de saude, spam de puzzles, "
            "regras KDP), e o que seria preciso para nos diferenciarmos. Separa factos medidos de estimativas. "
            "Nunca inventes numeros. Escreve relatorio_md em portugues, curto, com tabela dos 10 melhores livros. "
            "Da veredicto (entrar/testar/nao_entrar) e confianca 0-100."), ESQ_PESQ, pasta, f"{pasta}/analise.json")
        open(f"{pasta}/RELATORIO.md", "w").write(f"# Pesquisa: {t['id']}\n\nVeredicto: {a['veredicto']} "
                                                  f"(confianca {a['confianca']}%)\n\n{a['relatorio_md']}\n")
    a = lj(f"{pasta}/analise.json")
    if not ap.get("decidido"):
        portao(nome, "decidir", f"Pesquisa pronta: veredicto {a['veredicto']} ({a['confianca']}%). Decidir se entramos.",
               [f"{pasta}/RELATORIO.md"])
        return "portao"
    return "feito"


# ----------------------------------------------------------------- ciclo
def relatorio():
    os.makedirs(os.path.dirname(REL), exist_ok=True)
    p = ["# Decisoes pendentes (humano)", "", f"Atualizado {time.strftime('%Y-%m-%d %H:%M')} pela fabrica.", ""]
    for d in pendentes or [{"tarefa": "-", "decisao": "-", "texto": "Nada pendente.", "ficheiros": []}]:
        p.append(f"- **{d['tarefa']}** [{d['decisao']}]: {d['texto']}")
        for f in d["ficheiros"]:
            p.append(f"  - {f}")
    open(PEND, "w").write("\n".join(p) + "\n")
    r = ["# Fabrica: estado", "", f"Atualizado {time.strftime('%Y-%m-%d %H:%M')}. Gasto do mes: US$ {gasto_mes():.2f} "
         f"(teto US$ {TETO_MES}).", "", "| Tarefa | Estado |", "|---|---|"] + linhas_rel
    open(REL, "w").write("\n".join(r) + "\n")


def commit():
    run(["git", "add", "-A", "decisoes/pendentes.md", "relatorios/fabrica.md", "fila", "projetos", "gastos.jsonl", "melhorias.md", "config.json", "decisoes"], cwd=EMP)
    if run(["git", "diff", "--cached", "--quiet"], cwd=EMP).returncode:
        run(["git", "commit", "-qm", "Fabrica: estado " + time.strftime("%Y-%m-%d %H:%M")], cwd=EMP)
        run(["git", "push", "-q"], cwd=EMP, timeout=120)


def main():
    os.makedirs(FILA, exist_ok=True)
    open(GASTOS, "a").close()
    lock = f"{LIV}/.fabrica.lock"
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 8 * 3600:
        log("outra execucao em curso; saio"); return
    open(lock, "w").write(str(os.getpid()))
    try:
        for f in sorted(glob.glob(f"{FILA}/*.json")):
            t = lj(f)
            nome = os.path.basename(f)[:-5]
            if t.get("estado") == "feito":
                linhas_rel.append(f"| {nome} | feito |"); continue
            try:
                if "--estado" in sys.argv:
                    res = t.get("estado", "?")
                else:
                    res = (livro if t["tipo"] == "livro" else pesquisa)(t, nome)
                    t["estado"], t["erro"] = res, None
            except Exception as e:  # erro numa tarefa nao para as outras
                t["estado"], t["erro"] = "erro", str(e)[:500]
                portao(nome, "erro", f"A fabrica parou nesta tarefa: {t['erro']}")
                res = "erro"
            t["atualizado"] = time.strftime("%Y-%m-%d %H:%M")
            gj(f, t)
            linhas_rel.append(f"| {nome} | {res} |")
            log(nome, "->", res)
        relatorio()
        commit()
    finally:
        os.remove(lock)


if __name__ == "__main__":
    main()
