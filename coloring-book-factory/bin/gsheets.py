#!/usr/bin/env python3
"""Google Sheets access with the token of the rclone remote 'personal' (drive scope).
Never prints tokens or secrets."""
import configparser, json, subprocess, sys, urllib.parse, urllib.request, os

RCLONE = os.path.expanduser("~/.local/bin/rclone")

def token():
    path = subprocess.run([RCLONE, "config", "file"], capture_output=True, text=True).stdout.strip().splitlines()[-1]
    c = configparser.ConfigParser(); c.read(path)
    s = c["personal"]
    tok = json.loads(s["token"])
    data = urllib.parse.urlencode({"client_id": s["client_id"], "client_secret": s["client_secret"],
                                   "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data)) as r:
        return json.loads(r.read())["access_token"]

def api(method, url, body=None, tk=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {tk}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")

BASE = "https://sheets.googleapis.com/v4/spreadsheets/"

if __name__ == "__main__":
    sid = sys.argv[1]
    tk = token()
    meta = api("GET", BASE + sid + "?fields=properties.title,sheets.properties", tk=tk)
    print("TITLE:", meta["properties"]["title"])
    for sh in meta["sheets"]:
        p = sh["properties"]; t = p["title"]
        print(f"\n== TAB: {t} ({p['gridProperties']['rowCount']}x{p['gridProperties']['columnCount']})")
        v = api("GET", BASE + sid + "/values/" + urllib.parse.quote(f"'{t}'!A1:Z60"), tk=tk).get("values", [])
        for row in v[:60]:
            print(" | ".join(row))
