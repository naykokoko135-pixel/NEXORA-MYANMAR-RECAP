import os
from openai import AsyncOpenAI


async def generate_recap_outline(topic: str) -> str:
    """
    Generate an original Burmese-language recap commentary outline with Grok.
    Use only licensed, public-domain, or user-provided source material.
    Avoid detailed scene-by-scene retellings that substitute for the original.
    """
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("XAI_API_KEY is missing")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1",
        timeout=120.0,
    )
    prompt = f"""
သင်သည် မြန်မာဘာသာ Recap အယ်ဒီတာဖြစ်သည်။
ခေါင်းစဉ်/အကြောင်းအရာ: {topic}

မူရင်းသုံးသပ်ချက်နှင့် အကျဉ်းချုပ် outline ကို မြန်မာဘာသာဖြင့် ရေးပါ။
- သဘာဝကျပြီး နားထောင်လို့ကောင်းသော narration ပုံစံကို သုံးပါ။
- Spoiler warning ထည့်ပါ။
- အဓိကဇာတ်ကောင်၊ အဓိကအကြောင်းအရာ၊ theme နှင့် ကိုယ်ပိုင်သုံးသပ်ချက်ကို ဦးစားပေးပါ။
- အတည်မပြုနိုင်သော အချက်အလက်ကို မဖန်တီးပါနှင့်။ စစ်ဆေးရန်လိုလျှင် [VERIFY] ဟု မှတ်သားပါ။
- ဇာတ်ဝင်ခန်းတစ်ခန်းချင်းစီကို အစဉ်လိုက် အသေးစိတ်ပြန်မရေးပါနှင့်။
- မူပိုင်ခွင့်ရှိသော dialogue၊ ဇာတ်ညွှန်း သို့မဟုတ် အခြားသူ၏ recap စာသားကို မကူးယူပါနှင့်။
- 30–45 မိနစ် video အတွက် အပိုင်းခွဲ outline၊ intro၊ commentary၊ conclusion နှင့် CTA ထည့်ပါ။
- source material အသုံးပြုခွင့် မသေချာပါက သတိပေးချက် ထည့်ပါ။
- အသုံးပြုသူပေးထားသည့် အကြောင်းအရာထက်ကျော်လွန်၍ မသိသော plot details မခန့်မှန်းပါနှင့်။
"""

    response = await client.chat.completions.create(
        model=os.getenv("XAI_MODEL", "grok-4.7"),
        messages=[
            {
                "role": "system",
                "content": (
                    "You write original, factual Burmese film commentary and recap "
                    "outlines. Do not invent facts or reproduce copyrighted expression."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
    )
    return response.choices[0].message.content or "Outline မရရှိပါ။"
