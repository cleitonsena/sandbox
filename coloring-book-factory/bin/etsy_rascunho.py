#!/usr/bin/env python3
"""Cria um RASCUNHO de anuncio na loja Etsy MySandboxBooks a partir de kit/etsy/anuncio.json.
Nunca publica: nao existe neste ficheiro nenhuma chamada que mude o estado do anuncio. Quem publica e o Cleiton.
Decisoes 0004 e 0013. Etsy Open API v3 (spec oficial lida a 22 Nov 2026).

Uso:  etsy_rascunho.py <pasta-do-livro> --seco   (valida tudo, sem rede)
      etsy_rascunho.py <pasta-do-livro>          (cria o rascunho; precisa de ~/empresa/.segredos/etsy.json)
"""
import json, mimetypes, os, re, subprocess, sys, urllib.error, urllib.parse, urllib.request, uuid

API = "https://api.etsy.com/v3"
SEG = os.path.expanduser("~/empresa/.segredos/etsy.json")
pasta = os.path.abspath(sys.argv[1])
SECO = "--seco" in sys.argv
kit = f"{pasta}/kit"
AJ = f"{kit}/etsy/anuncio.json"
a = json.load(open(AJ))

# 1. Validacao com as regras da spec oficial
erros = []
t = a["titulo"]
if len(t) > 140: erros.append("titulo > 140")
if re.search(r"[^\w\s\.,;:!\?'\"\-\(\)&%+/]", t): erros.append("titulo com caracteres fora da regra")
for c in "%:&+":
    if t.count(c) > 1: erros.append(f"titulo usa '{c}' mais de 1 vez")
tags = a["tags"]
if len(tags) > 13: erros.append("mais de 13 tags")
for g in tags:
    if len(g) > 20 or re.search(r"[^\w\s\-']", g) or "_" in g: erros.append(f"tag invalida: {g}")
preco = (a.get("preco") or {}).get("eur")
if not preco or "aprovado" not in (a.get("preco") or {}).get("estado", ""): erros.append("preco sem aprovacao do Cleiton")
ficheiro = f"{kit}/imprimivel.pdf"
if not os.path.exists(ficheiro) or os.path.getsize(ficheiro) > 20 * 1024 * 1024: erros.append("imprimivel.pdf em falta ou > 20MB")
fotos = []
os.makedirs(f"{kit}/etsy/fotos", exist_ok=True)
for i, f in enumerate(a["fotos"], 1):
    src, dst = f"{kit}/{f}", f"{kit}/etsy/fotos/{i:02d}.jpg"
    if not os.path.exists(src):
        erros.append(f"foto em falta: {f}"); continue
    if not os.path.exists(dst):
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90", "-Z", "2700", src, "--out", dst],
                       check=True, capture_output=True)
    fotos.append(dst)
if len(fotos) > 20: erros.append("mais de 20 fotos")
if a.get("listing_id"): erros.append(f"ja existe rascunho {a['listing_id']}; nao crio outro")
if erros:
    sys.exit("PAROU:\n- " + "\n- ".join(erros))

corpo = {"quantity": a.get("quantidade", 999), "title": t, "description": a["descricao"], "price": preco,
         "who_made": a.get("who_made", "i_did"), "when_made": a.get("when_made", "2020_2026"), "is_supply": "false",
         "type": "download", "should_auto_renew": "false", "tags": ",".join(tags)}
print(f"OK validacao: titulo {len(t)} car., {len(tags)} tags, preco EUR {preco}, {len(fotos)} fotos, "
      f"PDF {os.path.getsize(ficheiro) / 1e6:.1f} MB")
if SECO:
    print("Modo seco: nada enviado ao Etsy.\n" + json.dumps({k: v for k, v in corpo.items() if k != "description"}, indent=1))
    sys.exit(0)

# 2. Acesso: refresh token (o Etsy devolve um novo a cada uso; gravamos logo)
s = json.load(open(SEG))
r = urllib.request.urlopen(urllib.request.Request(f"{API}/public/oauth/token", data=urllib.parse.urlencode(
    {"grant_type": "refresh_token", "client_id": s["keystring"], "refresh_token": s["refresh_token"]}).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=30)
tok = json.loads(r.read())
s["refresh_token"] = tok["refresh_token"]
fd = os.open(SEG, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, 0o600)
os.write(fd, json.dumps(s).encode()); os.close(fd)
H = {"x-api-key": f"{s['keystring']}:{s['shared_secret']}", "Authorization": f"Bearer {tok['access_token']}"}


def chamar(metodo, caminho, form=None, multipart=None):
    h, dados = dict(H), None
    if form is not None:
        h["Content-Type"] = "application/x-www-form-urlencoded"
        dados = urllib.parse.urlencode(form).encode()
    if multipart is not None:
        b = uuid.uuid4().hex; partes = []
        for k, v in multipart.items():
            if isinstance(v, tuple):
                nome, conteudo = v
                partes.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{nome}"\r\n'
                              f'Content-Type: {mimetypes.guess_type(nome)[0] or "application/octet-stream"}\r\n\r\n'.encode() + conteudo + b"\r\n")
            else:
                partes.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        dados = b"".join(partes) + f"--{b}--\r\n".encode()
        h["Content-Type"] = f"multipart/form-data; boundary={b}"
    try:
        with urllib.request.urlopen(urllib.request.Request(API + caminho, data=dados, headers=h, method=metodo), timeout=300) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"PAROU: {metodo} {caminho} HTTP {e.code}: {e.read().decode()[:400]}")


shop = chamar("GET", "/application/users/me")["shop_id"]

# 3. Categoria: procura "Coloring Books" na arvore oficial; so segue com 1 resultado exacto
if not a.get("taxonomy_id"):
    achados = []
    def andar(nos):
        for n in nos:
            if n.get("name", "").strip().lower() == "coloring books":
                achados.append((n["id"], " > ".join(str(x) for x in n.get("full_path_taxonomy_ids", []))))
            andar(n.get("children") or [])
    andar(chamar("GET", "/application/seller-taxonomy/nodes").get("results", []))
    if len(achados) != 1:
        sys.exit(f"PAROU: categoria 'Coloring Books' encontrada {len(achados)} vezes: {achados}. Escolher a mao.")
    a["taxonomy_id"] = achados[0][0]
corpo["taxonomy_id"] = a["taxonomy_id"]

# 4. Rascunho + fotos + ficheiro digital
lst = chamar("POST", f"/application/shops/{shop}/listings", form=corpo)
lid = lst["listing_id"]
a["listing_id"] = lid
a["estado_etsy"] = "rascunho criado pelo bot; Cleiton revê e publica"
json.dump(a, open(AJ, "w"), indent=1, ensure_ascii=False)
for i, f in enumerate(fotos, 1):
    chamar("POST", f"/application/shops/{shop}/listings/{lid}/images",
           multipart={"image": (os.path.basename(f), open(f, "rb").read()), "rank": str(i),
                      "alt_text": a.get("alt_fotos", ["Coloring book page preview"] * 20)[i - 1] if a.get("alt_fotos") else "Cozy coloring book page preview"})
chamar("POST", f"/application/shops/{shop}/listings/{lid}/files",
       multipart={"file": (f"{a.get('nome_ficheiro', 'Cozy Little Corners')}.pdf", open(ficheiro, "rb").read()),
                  "name": f"{a.get('nome_ficheiro', 'Cozy Little Corners')}.pdf", "rank": "1"})
fim = chamar("GET", f"/application/listings/{lid}")
print(f"Rascunho criado: listing {lid}, estado '{fim.get('state')}', preco {fim.get('price')}. "
      f"Rever em https://www.etsy.com/your/shops/me/listing-editor/edit/{lid}")
