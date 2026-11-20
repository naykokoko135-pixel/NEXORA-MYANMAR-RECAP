# Colab Free GPU မှ VoxCPM2 အသံထုတ်ပြီး NEXORA ထဲသို့ သွင်းခြင်း

## ဘာကြောင့် ဒီလမ်းကြောင်းလိုသလဲ

NEXORA ၏ `/voiceclone` သည် Bot server ပေါ်တွင် VoxCPM2 ကို တိုက်ရိုက် run လုပ်သောကြောင့် CUDA GPU လိုအပ်သည်။ Render Free တွင် GPU မရှိသဖြင့် ထို command ဖြင့် WAV မထုတ်နိုင်ပါ။ အခမဲ့အစားထိုးလမ်းကြောင်းမှာ Google Colab GPU runtime တွင် ကိုယ်ပိုင် Reference အသံဖြင့် WAV/MP3 ထုတ်ပြီး၊ MP3 ကို NEXORA ၏ render workflow ထဲသို့ ထည့်ခြင်းဖြစ်သည်။

Google Colab Free တွင် GPU ရရှိမှုနှင့် အသုံးပြုချိန်ကို အာမမခံနိုင်ပါ။ Model ကို ပထမဆုံးအကြိမ် download လုပ်ရမည်။ အခကြေးငွေရှိသော GPU service မလိုအပ်ဘဲ မဖွင့်ပါနှင့်။

## Colab အဆင့်များ

1. Notebook `NEXORA_VoxCPM2_Myanmar_Voice_Clone_Free_GPU.ipynb` ကို Google Colab တွင် ဖွင့်ပါ။
2. Runtime → Change runtime type → T4 GPU ရွေးပါ (ရရှိနိုင်မှသာ)။
3. Install cell ကို run ပါ။
4. Upload cell တွင် ကိုယ်ပိုင် `NEXORA_voice_clone.wav` reference ဖိုင်ကို upload လုပ်ပါ။ PCM 16-bit WAV ဖြစ်ရမည်။
5. `SCRIPTS` ထဲတွင် စမ်းဖတ်မည့် မြန်မာစာသားကို ထည့်ပြီး model generation cell ကို run ပါ။
6. WAV မူရင်းနှင့် Telegram ပို့ရန် 96 kbps MP3 ထုတ်ပေးမည်။ MP3 တစ်ဖိုင်စီ 20 MB အောက်ဖြစ်ကြောင်း စစ်ပါ။ 20 MB ကျော်ပါက စာသားကို ပိုတိုသော အပိုင်းများခွဲ၍ ထပ်ထုတ်ပါ။
7. Colab runtime အခမဲ့ GPU မရပါက နောက်မှ ပြန်စမ်းပါ။ GPU ကို ဝယ်ယူရန် မလိုအပ်ပါ။

## NEXORA Bot ထဲသို့ MP3 သွင်းခြင်း

NEXORA ၏ `/render timeline` သည် Scene တစ်ခုစီအတွက် ပုံတစ်ပုံနှင့် အသံတစ်ဖိုင် လက်ခံသည်။ ယခု render document handler သည် `.wav`, `.mp3`, `.m4a`, `.ogg` နှင့် `.srt` ကို Document အဖြစ် ပို့လျှင်လည်း ခွဲခြားလက်ခံနိုင်သည်။

### YouTube/Facebook သုံးပိုင်း Recap

1. Telegram Bot တွင် `/render timeline` ပို့ပါ။
2. `/render scene Part 1` ပို့ပြီး Part 1 အတွက် အသုံးပြုခွင့်ရှိသော ပုံတစ်ပုံနှင့် Colab မှ Part 1 MP3 ကို Document အဖြစ် ပို့ပါ။
3. Part 2 နှင့် Part 3 ကိုလည်း အလားတူ ထည့်ပါ။ တစ် Scene လျှင် ပုံတစ်ပုံ + MP3 တစ်ဖိုင် ဖြစ်ရမည်။
4. SRT ရှိပါက `.srt` ဖိုင်ကို ပို့ပါ။
5. `/render finish` ပို့ပါ။ NEXORA သည် Scene များကို အစဉ်လိုက်ပေါင်း၍ MP4 Preview ထုတ်ပေးမည်။

### TikTok တစ်ဖိုင်

1. `/render timeline` ပို့ပါ။
2. `/render scene TikTok` ပို့ပါ။
3. ပုံတစ်ပုံနှင့် Colab မှ MP3 တစ်ဖိုင် ပို့ပါ။
4. SRT ရှိပါက ပို့ပြီး `/render finish` ပို့ပါ။

## အရေးကြီးသော ကန့်သတ်ချက်များ

- `/voiceprofile` သည် Reference အသံကို သိမ်းဆည်းရန်ဖြစ်သည်။ Colab ထုတ်ထားသော narration MP3 ကို Voice Profile အဖြစ် ပြန်သိမ်းခြင်းနှင့် မတူပါ။
- Colab မှထုတ်ထားသော MP3 ကို NEXORA က အသံဖိုင်အဖြစ် အသုံးပြုမည်။ Bot ပေါ်တွင် ထို MP3 ကို စာသားအသစ်အဖြစ် ပြန် TTS မလုပ်ပါ။
- ဒီလမ်းကြောင်းက word-aligned SRT ကို အလိုအလျောက် မဖန်တီးပါ။ SRT မရှိလျှင် subtitle မပါဘဲ MP4 ထုတ်နိုင်သည်။ `/srtmy` သည် ခန့်မှန်းအချိန် SRT ဖြစ်ပြီး word alignment မဟုတ်ပါ။
- Render session သည် ပုံ ၁၂ ပုံအထိ၊ Scene ၁၂ ခုအထိ၊ အသံတစ်ဖိုင်လျှင် 20 MB အောက်ကို လက်ခံသည်။
- အသံအရည်အသွေး၊ မြန်မာအသံထွက်၊ နာမည်အသံထွက်နှင့် အကြောင်းအရာမှန်ကန်မှုကို ထုတ်ဝေမီ လူကိုယ်တိုင် နားထောင်စစ်ဆေးပါ။
- ကိုယ်ပိုင် သို့မဟုတ် အသုံးပြုခွင့်ရှိသော Reference အသံ၊ Script၊ ပုံများကိုသာ အသုံးပြုပါ။
