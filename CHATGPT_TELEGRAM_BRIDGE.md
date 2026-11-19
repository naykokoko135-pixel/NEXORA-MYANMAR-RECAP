# ChatGPT ↔ Telegram Bridge

This optional bridge lets a supported Custom GPT Action invoke the NEXORA command allow-list and send supported files to the owner's configured private Telegram chat. It does **not** connect the ordinary ChatGPT conversation automatically. Availability of GPT Actions depends on the current ChatGPT account/workspace and editor features.

## Render Environment configuration

After the code is deployed, open the NEXORA web service in Render → Environment and add:

- `CHATGPT_BRIDGE_API_KEY`: a newly generated, long random secret (at least 32 characters). Keep it private; do not paste it into ChatGPT messages, Telegram, GitHub, or screenshots.
- `CHATGPT_BRIDGE_CHAT_ID`: the numeric private chat ID returned by sending `/chatid` to @NexoraMyanmarRecapBot. Use it only as the bridge destination.

Do not reuse the Telegram Bot Token as the bridge key. Never commit either value. Save changes and redeploy.

## Custom GPT Action setup

1. In an eligible GPT editor that supports Actions, open the GPT's Actions configuration.
2. Import the canonical schema `chatgpt_action_openapi.yaml`.
3. Replace `https://YOUR-RENDER-SERVICE.onrender.com` with the actual Render service URL (HTTPS).
4. Set Authentication to API Key, header name `X-Nexora-Bridge-Key`, and enter the same `CHATGPT_BRIDGE_API_KEY` value configured in Render.
5. Save and test `checkNexoraBridge`; then test `sendNexoraCommand` with `status`.

## Supported operations

- `GET /chatgpt/bridge-health` — reports whether Telegram and bridge configuration are ready; does not expose secret values.
- `POST /chatgpt/command` — dispatches one allow-listed, single-line command to the configured private chat.
- `POST /chatgpt/send-file` — sends one supported file (maximum 20 MB) to the configured private chat.

The command allow-list is maintained in `bot.py` and mirrored in the canonical OpenAPI schema. It includes status/help, research and worksheet commands, recap-video and licensed-footage discovery commands, and multi-source catalogue research. The schema is the authoritative list of exact command names.

File sending accepts only `.mp3`, `.wav`, `.ogg`, `.jpg`, `.jpeg`, `.png`, `.webp`, `.mp4`, `.txt`, and `.srt` files, with a decoded size limit of 20 MB. Use only files and media you own or have permission to use.

## Important limitations and security

- The bridge does not expose arbitrary shell commands, arbitrary Telegram chat IDs, or arbitrary Telegram Bot API methods.
- Command arguments are single-line and limited to 3,500 characters. Multi-line narration and interactive upload flows must still be completed in Telegram.
- A successful HTTP response confirms dispatch to the bot handler; it does not guarantee that a recap video or media asset was generated.
- The Action works only in the GPT where it is configured and only when that GPT invokes it. It does not grant this ordinary ChatGPT chat a persistent Telegram connector.
- Keep the bridge key private. If exposed, rotate it in Render and in the GPT Action authentication settings.

## Mobile web console alternative

When GPT Actions are unavailable, the owner can use the mobile command console at `/console`. Set a separate `NEXORA_CONSOLE_PASSWORD` in Render Environment (at least 16 characters), redeploy, then sign in at the Render service's `/console` URL. The console uses the already configured private `CHATGPT_BRIDGE_CHAT_ID`, a server-verified password, an eight-hour signed HttpOnly/Secure/SameSite cookie, same-origin POST checks, and the same command allow-list. The password is never stored in browser JavaScript or sent to Telegram. Do not reuse either Telegram Bot Token or `CHATGPT_BRIDGE_API_KEY` as the console password.

This is a manual handoff: ChatGPT drafts a command, and the owner pastes it into the console. It does not create a direct connector from an ordinary ChatGPT conversation. Multi-line narration and interactive file workflows remain Telegram-only.
