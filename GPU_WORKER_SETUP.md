# NEXORA VoxCPM2 GPU Worker (optional)

The Telegram bot can keep running on Render Free. VoxCPM2 inference runs on a separate, on-demand Modal GPU worker. The worker is configured for an NVIDIA L4 and scales down after idle time. GPU runtime, model downloads/storage, and provider charges are controlled by Modal, not Render.

## 1. Create the worker secret

Create a long random token locally; do not paste it into GitHub, Telegram, or ChatGPT:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Install and authenticate Modal:

```bash
python -m pip install modal
modal setup
modal secret create nexora-voxcpm-secret NEXORA_VOXCPM_WORKER_TOKEN='PASTE_TOKEN_LOCALLY'
```

Use the exact same token value in the Render environment variable in step 3. Keep it private.

## 2. Deploy the GPU worker

From the repository root:

```bash
modal deploy modal_voxcpm_worker.py
```

Modal prints an HTTPS endpoint URL for the synthesize web endpoint. Copy that URL; do not add a trailing slash unless Modal prints one.

## 3. Configure the existing Render web service

In Render → nexora-myanmar-recap-bot → Environment, add:

- NEXORA_VOXCPM_GPU_URL: the HTTPS endpoint URL printed by Modal
- NEXORA_VOXCPM_WORKER_TOKEN: the same random token used in the Modal secret

Save changes and let Render redeploy. No Render GPU upgrade is needed. The default render.yaml remains on Free. The optional persistent Render blueprint is separate and only needed if voice-profile SQLite data must survive Render restarts; it is not required to run the remote GPU worker.

## 4. Test in Telegram

- /tts_design story_male followed by Burmese text when prompted: tests fictional voice design.
- /voiceclone <profile_name> with a previously saved, creator-consented reference profile: tests personal voice cloning.

The first request can be slower because Modal downloads/loads the VoxCPM2 model. Later requests may be faster while the worker remains warm. An idle worker scales down and a later request may cold-start. Monitor Modal usage and set provider spending limits/alerts before regular production.

## Security and limits

- Only use voice samples you own or have explicit permission to use.
- The worker checks a shared secret and accepts bounded text/audio input.
- Do not expose the token in source code, public logs, or chat.
- A GPU worker does not restore lost voice profiles. If /voiceprofile list is empty, upload the sample again or import a previously exported backup.
- This is an optional paid GPU service; deployment is not performed automatically from this repository.
