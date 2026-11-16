import os
from openai import AsyncOpenAI

async def generate_recap_outline(topic: str) -> str:
    """
    Generates an original Burmese-language recap commentary outline.
    Use only licensed, public-domain, or user-provided source material.
    Avoid scene-by-scene retellings that substitute for the original work.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    client = AsyncOpenAI(api_key=api_key)
    prompt = f"""
သင်သည် မြန်မာဘာသာ Recap အယ်ဒီတာဖြစ်သည်။
ခေါင်းစဉ်/အကြောင်းအရာ: {topic}

အောက်ပါပုံစံဖြင့် မူရင်းသုံးသပ်ချက်နှင့် အကျဉ်းချုပ် outline ရေးပါ။
- မြန်မာဘာသာ၊ သဘာဝကျသော အမျိုးသား narration အတွက် သင့်တော်သော စာသား
- Spoiler warning ထည့်ပါ
- အဓိကဇာတ်ကောင်၊ အကြောင်းအရာ၊ theme နှင့် ကိုယ်ပိုင်သုံးသပ်ချက်ကို ဖော်ပြပါ
- မသိသော အချက်အလက်များကို မဖန်တီးပါနှင့်
- ဇာတ်ဝင်ခန်းတစ်ခန်းချင်းစီကို အသေးစိတ်ပြန်မရေးပါနှင့်
- မူပိုင်ခွင့်ရှိသော ဇာတ်ညွှန်း၊ dialogue သို့မဟုတ် footage ကို မကူးယူပါနှင့်
- အချက်အလက်စစ်ဆေးရန် လိုအပ်သည့်နေရာများကို [VERIFY] ဟု မှတ်သားပါ
- 30–45 မိနစ် video အတွက် အပိုင်းခွဲ outline၊ intro၊ commentary၊ conclusion နှင့် CTA ပေးပါ
- source material သို့မဟုတ် အသုံးပြုခွင့် မသေချာပါက ထိုအချက်ကို ရှင်းလင်းဖော်ပြပါ
"""
    response = await client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        messages=[
            {"role": "system", "content": "You write original, factual Burmese film commentary and recap outlines."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
    )
    return response.choices[0].message.content or "Outline မရရှိပါ။"
