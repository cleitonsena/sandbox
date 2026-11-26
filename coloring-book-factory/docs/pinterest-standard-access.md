# Pinterest Standard access: demo video

How to record the video that Pinterest asks for before it upgrades an app from Trial to Standard access,
using `bin/pinterest.py`. Requirements are from the official docs, read on 26 Nov 2026
(https://developers.pinterest.com/docs/key-concepts/access-tiers/).

## What Pinterest asks for

- The app must **already have Trial access**. The app secret is not shown in My apps before that, so the
  OAuth flow cannot run.
- A video of the app doing an action with the API that **shows the OAuth flow**. This applies even when you
  are the only user. Screen recordings of a terminal are accepted.
- No passwords and no session cookies: only an OAuth access token.

## Before recording (once, after Trial is approved)

1. In My apps > your app > Configure:
   - copy the **app ID** and the **app secret** into `~/.pinterest-app-id` and `~/.pinterest-secret`
     (chmod 600; never paste them into the terminal history);
   - under **Redirect URIs**, add `http://localhost:8085/` (it must match exactly).
2. Check that the board named in the pin you will publish exists on your account.
3. Close tabs with personal data. Make the terminal font large.

## Recording (about 2 minutes)

On macOS, press Cmd+Shift+5 and record the whole screen, so the terminal and the browser are both visible.
Run the commands on the same machine as the browser.

1. `python3 bin/pinterest.py connect`
2. The Pinterest page opens with the app name and the scopes. Leave it on screen for 3 seconds, then click
   **Give access**.
3. The browser shows "authorization received". Back in the terminal you see "state matches" and
   "Token saved ... The value is not shown".
4. `python3 bin/pinterest.py me` (shows the connected account)
5. `python3 bin/pinterest.py boards`
6. `python3 bin/pinterest.py publish <book> 1`
7. Open the pin link printed at the end and show the pin on Pinterest.

With Trial access the pin is visible only to you. That is expected, and it is enough for the video.

## Submitting

My apps > app card > **Upgrade** > check the details > upload the video > Submit.
