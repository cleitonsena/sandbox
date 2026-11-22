#!/usr/bin/env python3
"""Edita/amplia uma imagem via OpenAI Images API (endpoint edits).
Uso: editar_imagem.py MODELO QUALIDADE TAMANHO ENTRADA.png SAIDA.png "prompt"
A chave vive em ~/.openai-imagens (chmod 600) e nunca e impressa."""
import base64, json, os, sys, time, urllib.error, urllib.request, uuid

model, quality, size, src, out, prompt = sys.argv[1:7]
with open(os.path.expanduser("~/.openai-imagens")) as f:
    key = f.read().strip()
b = uuid.uuid4().hex
partes = []
for k, v in [("model", model), ("quality", quality), ("size", size), ("prompt", prompt)]:
    partes.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
partes.append(f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="in.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
              + open(src, "rb").read() + b"\r\n")
partes.append(f"--{b}--\r\n".encode())
req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=b"".join(partes),
                             headers={"Content-Type": f"multipart/form-data; boundary={b}",
                                      "Authorization": "Bearer " + key})
del key
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
except urllib.error.HTTPError as e:
    print(json.dumps({"erro": e.code, "detalhe": e.read()[:400].decode("utf-8", "replace")}))
    sys.exit(1)
with open(out, "wb") as f:
    f.write(base64.b64decode(d["data"][0]["b64_json"]))
print(json.dumps({"segundos": round(time.time() - t0, 1), "ficheiro": out, "usage": d.get("usage")}))
