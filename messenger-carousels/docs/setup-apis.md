# API key setup (26 Nov 2026)

The engine (`carousel_auto.py`) already runs on its own. Without keys, each network stays in `dry-run` and nothing goes out.
When a key arrives, that network starts publishing on the next cycle (15 min). All of this is human work:
creating accounts, apps and payments. Keys never go through a chat.

Save each key as a file in your home folder, one value per file, `chmod 600`:

    read -rs V; (umask 077; printf '%s' "$V" > ~/.NAME); unset V; chmod 600 ~/.NAME

## 1. Zernio (TikTok, Instagram and image hosting)
1. Create an account at zernio.com (free plan).
2. Connect the TikTok account.
3. Create an API key (starts with `sk_`).
4. Save it as `~/.zernio-key`.

## 2. Instagram (also through Zernio, second free account)
1. The Instagram account must be Business or Creator.
2. In Zernio, connect Instagram through "Instagram Login" (no Facebook page needed).
3. No new key: it uses the same `~/.zernio-key`. The post goes out with the AI label (`isAiGenerated`).

## 3. X (official API, paid)
1. At developer.x.com create a project and an app dedicated to this profile (never reuse keys from another project).
2. App permissions: Read and Write. Generate the OAuth 1.0a keys: API Key, API Key Secret, Access Token, Access Token Secret.
3. Buy credits (pay per use, about USD 0.015 per post without a link; 3 a day comes to about USD 1.4 a month).
4. Save them as `~/.x-ck` (API Key), `~/.x-cs` (API Key Secret), `~/.x-at` (Access Token), `~/.x-as` (Access Token Secret).
   Alternatively, get the Access Token and Secret with `bin/x_pin.py` (PIN flow), logged in on x.com as the posting account.

## Check the state
    python3 carousel_auto.py status
The log goes to `~/company/log.md`. The first real post on each network should be checked by eye.
