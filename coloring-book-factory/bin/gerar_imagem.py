#!/usr/bin/env python3
"""Gera uma pagina de colorir via OpenAI Images API (decisao 0007).
Uso: gerar_imagem.py MODELO QUALIDADE SAIDA.png "prompt"
A chave vive em ~/.openai-imagens (chmod 600) e nunca e impressa."""
import base64, json, os, sys, time, urllib.error, urllib.request

model, quality, out, prompt = sys.argv[1:5]
with open(os.path.expanduser("~/.openai-imagens")) as f:
    key = f.read().strip()
body = json.dumps({"model": model, "prompt": prompt, "n": 1,
                   "size": os.environ.get("TAMANHO") or "1024x1536", "quality": quality}).encode()
req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body,
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Bearer " + key})
del key
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
except urllib.error.HTTPError as e:
    print(json.dumps({"modelo": model, "qualidade": quality, "erro": e.code,
                      "detalhe": e.read()[:400].decode("utf-8", "replace")}))
    sys.exit(1)
secs = round(time.time() - t0, 1)
with open(out, "wb") as f:
    f.write(base64.b64decode(d["data"][0]["b64_json"]))
print(json.dumps({"modelo": model, "qualidade": quality, "segundos": secs,
                  "ficheiro": out, "usage": d.get("usage")}))
