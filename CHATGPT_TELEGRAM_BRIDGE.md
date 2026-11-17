# ChatGPT ↔ Telegram Bridge

This optional bridge lets a **Custom GPT Action** invoke a small allow-list of NEXORA commands and send supported files to the owner's private Telegram chat. It does not make the ordinary ChatGPT conversation automatically connected; configure a Custom GPT Action using the OpenAPI document in `openapi-chatgpt-bridge.yaml`.

## Render Environment configuration

After this PR is merged and deployed, open the NEXORA web service in Render → Environment and add:

- `CHATGPT_BRIDGE_API_KEY`: a newly generated, long random secret (at least 32 random bytes). Keep it private; do not paste it into ChatGPT messages, Telegram, GitHub, or screenshots.
- `CHATGPT_BRIDGE_CHAT_ID`: the numeric private chat ID returned by sending `/chatid` to @NexoraMyanmarRecapBot. This is a destination identifier, not a password; still keep it private.

Do not reuse the Telegram Bot Token as the bridge key. Never commit either value. Save and redeploy.

## Custom GPT Action setup

1. Create a Custom GPT and open its Actions configuration.
2. Import `openapi-chatgpt-bridge.yaml`.
3. Replace the server URL `https://YOUR-RENDER-SERVICE.onrender.com` with the actual Render service URL (HTTPS).
4. Set Authentication to API Key, header name `X-Nexora-Bridge-Key`, and enter the same `CHATGPT_BRIDGE_API_KEY` value configured in Render.
5. Save and test `status` first.

## Supported operations

- `status`, `help`
- `auto`, `create`, `research`, `draft3`, `voiceover3`
- `render` (starts the existing Telegram image/audio upload session)
- `send-file` (base64 JSON, maximum 20 MB; mp3/wav/ogg/jpg/jpeg/png/webp/mp4/txt/srt)

The bridge only accepts these named commands. It does not expose arbitrary shell commands, arbitrary Telegram chat IDs, or arbitrary bot API methods. File sending is limited to the configured private chat. Use only media you own or have permission to use.

## Important limitation

The Action works only in the Custom GPT where you configured it and only when that GPT invokes the Action. It does not grant this ordinary ChatGPT chat a persistent Telegram connector. Keep the bridge key private and rotate it in Render and the GPT Action settings if exposed.
