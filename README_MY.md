# Nexora Myanmar Recap Bot

## ဖွဲ့စည်းပုံ
- **Render Free** = Telegram control bot သာ (webhook၊ /health)
- **GitHub Actions** = အလုပ်ကြမ်းအားလုံး (research → script → TTS → SRT → ffmpeg render → QC → ပို့)
- Daily Auto: `0 22 * * *` UTC = Thailand 05:00 (pick → platform ၃ခု matrix)
- Visual အားလုံး ကိုယ်တိုင် generate (animated gradient + text + progress bar)၊ ပုံ/footage မသုံး

## တစ်ကြိမ်သာ setup (၁၀ မိနစ်)
1. ဒီ folder ကို repo ထဲ တင်ပါ (`main`)။
2. GitHub → Settings → Secrets → Actions: `GEMINI_API_KEY` (free: aistudio.google.com), `TMDB_API_KEY` (free), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   - 50MB ကျော်ဖိုင်: `R2_ACCOUNT_ID R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET` (Cloudflare R2 free tier) — မထည့်ရင် ၄၉MB အပိုင်းလိုက်ခွဲပို့
3. Render → New Blueprint → `render.yaml` (Free)။ Env: `TELEGRAM_BOT_TOKEN`, `GH_TOKEN` (fine-grained PAT: Actions + Contents read/write), `GEMINI_API_KEY`, `TMDB_API_KEY`
4. Telegram မှာ `/health` → အားလုံး ✅ ဖြစ်ရမယ်၊ `/create youtube` စမ်းပါ။
5. Auto-upload လိုချင်ရင် GitHub Variable `AUTO_UPLOAD=1` + YouTube/Facebook secrets (TikTok = caption ထုတ်ပေးပြီး manual)။

## မှန်ကန်စွာ သိထားရန်
- 46–60 မိနစ်ဆိုတာ Wikipedia source ပေါ်မူတည်ပါတယ်။ source မလုံလောက်ရင် bot က ညာမရေးဘဲ title ပြောင်းရွေး/fail report ပို့ပါတယ်။
- Voice clone: `VOICE_GPU_URL` (Modal worker) မထည့်မချင်း preset TTS သုံးပါတယ်။ GPU/paid deploy ကို သင့်ခွင့်ပြုချက်မရှိဘဲ မလုပ်ပါ။
- Voice profile persistence: `render.paid.yaml` (disk) သို့မဟုတ် R2 backup (`/voiceprofile export`)။
- ဒီ code ကို offline ပတ်ဝန်းကျင်မှာ unit test + ffmpeg render smoke test သာ စမ်းထားပါတယ်။ Live API (Gemini/TMDB/Telegram/Modal) ကို မစမ်းရသေးပါ — ပထမဆုံး run ကို `/create tiktok` နဲ့ စမ်းပါ။
