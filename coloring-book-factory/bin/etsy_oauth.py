#!/usr/bin/env python3
"""etsy_oauth (26 Nov 2026): authorises the MySandboxBooks shop in the shop's Etsy app (OAuth 2 + PKCE).
  etsy_oauth.py start          -> prints the authorisation link (stores verifier/state in ~/company/.secrets, 600)
  etsy_oauth.py finish "<URL>" -> swaps the code for the refresh token and writes ~/company/.secrets/etsy.json (600)
Reads ~/.etsy-keystring and ~/.etsy-secret. Never prints keys. Scopes: listings_r listings_w shops_r."""
import base64, hashlib, json, os, secrets, sys, urllib.parse, urllib.request
H = os.path.expanduser; D = H("~/company/.secrets"); RED = "http://localhost/etsy-callback"
ks = open(H("~/.etsy-keystring")).read().strip()


def write(p, d):
    fd = os.open(p, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, 0o600); os.write(fd, json.dumps(d).encode()); os.close(fd)


if sys.argv[1] == "start":
    v = secrets.token_urlsafe(64)[:96]; st = secrets.token_urlsafe(16)
    ch = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    write(f"{D}/etsy-pkce.json", {"v": v, "state": st})
    print("https://www.etsy.com/oauth/connect?" + urllib.parse.urlencode({
        "response_type": "code", "redirect_uri": RED, "scope": "listings_r listings_w shops_r", "client_id": ks,
        "state": st, "code_challenge": ch, "code_challenge_method": "S256"}, quote_via=urllib.parse.quote))
else:
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(sys.argv[2]).query)); pk = json.load(open(f"{D}/etsy-pkce.json"))
    if q.get("state") != pk["state"]: sys.exit("state does not match; run start again")
    r = urllib.request.urlopen(urllib.request.Request("https://api.etsy.com/v3/public/oauth/token", data=urllib.parse.urlencode(
        {"grant_type": "authorization_code", "client_id": ks, "redirect_uri": RED, "code": q["code"], "code_verifier": pk["v"]}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=30)
    t = json.loads(r.read())
    s = {"keystring": ks, "shared_secret": open(H("~/.etsy-secret")).read().strip(), "refresh_token": t["refresh_token"]}
    me = json.loads(urllib.request.urlopen(urllib.request.Request("https://api.etsy.com/v3/application/users/me", headers={
        "x-api-key": f"{ks}:{s['shared_secret']}", "Authorization": f"Bearer {t['access_token']}"}), timeout=30).read())
    s["shop_id"] = me.get("shop_id"); write(f"{D}/etsy.json", s); os.remove(f"{D}/etsy-pkce.json")
    print("OK: etsy.json written; shop_id", "present" if me.get("shop_id") else "MISSING")
