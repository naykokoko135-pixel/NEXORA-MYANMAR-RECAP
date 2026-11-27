"""TEST FIXTURE ONLY — used by ``python -m nexora.studio.acceptance --offline-fixture`` and the unit tests.

It stands in for the two network services that are unavailable in an offline sandbox (catalog/Wikipedia research and the AI script provider).
Everything *after* those two steps (queue, TTS, SRT, timeline, ffmpeg render, QC, publish draft, notification logic) runs for real.
The title is the CC-BY open movie "Big Buck Bunny" (Blender Foundation, 2008); the facts below are limited to well-known public
facts about it. The text is NOT intended for publication.
"""

SRC = {
    "title": "Big Buck Bunny", "alt": "Big Buck Bunny", "year": 2008, "country": "NL", "kind": "SHORT", "genres": ["Animation", "Comedy"],
    "popularity": 1, "catalog": "Blender Open Movies", "url": "https://peach.blender.org/", "hint": "film", "category": "3D Animation",
    "wiki_title": "Big Buck Bunny", "wiki_url": "https://en.wikipedia.org/wiki/Big_Buck_Bunny", "views": 0,
    "sources": ["Blender Open Movies (fixture)", "Wikipedia (fixture)"],
    "intro": ("Big Buck Bunny is a 2008 short computer-animated comedy film produced by the Blender Institute, directed by Sacha Goedegebure and "
              "produced by Ton Roosendaal. It was made with the open-source Blender software and released under a Creative Commons Attribution license. " * 3),
    "plot": ("A large, gentle rabbit lives in a peaceful meadow. Three rodents named Frank, Rinky and Gamera bully him and harm a butterfly he befriended. "
             "The rabbit then prepares slapstick traps built from natural objects to take his revenge. " * 4),
    "extras": {"production": "The film was the second open movie of the Blender Foundation, after Elephants Dream, and was followed by Sintel. " * 5},
}

S = [
    ("Introduction", "intro", [
        ("မင်္ဂလာပါ။ ဒီနေ့ဗီဒီယိုမှာ Big Buck Bunny ဆိုတဲ့ ကာတွန်းရုပ်ရှင်တိုလေးအကြောင်း ပြောပြပါမယ်။", "Hello. Today we talk about the short animated film Big Buck Bunny."),
        ("ဒီရုပ်ရှင်ကို ၂၀၀၈ ခုနှစ်မှာ ထုတ်လုပ်ခဲ့ပါတယ်။", "The film was produced in 2008."),
        ("အရှည်က ဆယ်မိနစ်လောက်ပဲ ရှိပါတယ်။", "It runs about ten minutes."),
        ("ဒါပေမယ့် လူတွေ အများကြီး သိကြပါတယ်။", "Yet many people know it."),
        ("ဘာကြောင့်လဲဆိုတော့ လွတ်လပ်စွာ ဝေမျှခွင့် ပေးထားတဲ့ ရုပ်ရှင်ဖြစ်လို့ပါ။", "Because it is a film released for open sharing."),
        ("အကြောင်းအရာကို အတိုချုပ် ပြောပြပေးပါမယ်။", "I will retell it briefly."),
        ("အဆုံးထိ ကြည့်ပေးပါနော်။", "Please watch until the end."),
        ("အခုဆို စတင်ကြည့်ရအောင်။", "Let us begin."),
    ]),
    ("About the film", "extra", [
        ("ဒီရုပ်ရှင်ကို Blender Institute က ထုတ်လုပ်ခဲ့ပါတယ်။", "The film was produced by the Blender Institute."),
        ("ဒါရိုက်တာက Sacha Goedegebure ဖြစ်ပါတယ်။", "The director is Sacha Goedegebure."),
        ("ထုတ်လုပ်သူက Ton Roosendaal ဖြစ်ပါတယ်။", "The producer is Ton Roosendaal."),
        ("ကွန်ပျူတာနဲ့ ရိုက်ကူးထားတဲ့ သုံးဖက်မြင် ကာတွန်းဖြစ်ပါတယ်။", "It is a computer-made three-dimensional animation."),
        ("အသုံးပြုခဲ့တဲ့ ဆော့ဖ်ဝဲက Blender ဖြစ်ပါတယ်။", "The software used was Blender."),
        ("Blender က အခမဲ့ အသုံးပြုနိုင်တဲ့ ဆော့ဖ်ဝဲဖြစ်ပါတယ်။", "Blender is free software."),
        ("ဒီရုပ်ရှင်ဟာ Blender ရဲ့ ဒုတိယမြောက် ဖွင့်ထားတဲ့ ရုပ်ရှင်ပါ။", "This was the second open movie from Blender."),
        ("ပထမတစ်ကားက Elephants Dream ဖြစ်ပါတယ်။", "The first was Elephants Dream."),
    ]),
    ("The meadow", "story", [
        ("ဇာတ်လမ်းက စိမ်းလန်းတဲ့ ကျယ်ဝန်းတဲ့ မြက်ခင်းပြင်မှာ စတင်ပါတယ်။", "The story begins in a wide green meadow."),
        ("နေရောင်ခြည်က လှပပြီး လေကလည်း အေးချမ်းပါတယ်။", "The sunlight is lovely and the air is calm."),
        ("အဲဒီမှာ ကြီးမားတဲ့ ယုန်တစ်ကောင် နေထိုင်ပါတယ်။", "A big rabbit lives there."),
        ("သူ့နာမည်က Big Buck Bunny ပါ။", "His name is Big Buck Bunny."),
        ("သူက ကိုယ်ကြီးပေမယ့် စိတ်သဘောထား နူးညံ့ပါတယ်။", "He is large but gentle."),
        ("မနက်ခင်းမှာ သူ အိပ်ရာက နိုးလာပါတယ်။", "In the morning he wakes up."),
        ("သူက သဘာဝကို ချစ်ပြီး ငြိမ်းချမ်းတဲ့ နေ့ရက်ကို နှစ်သက်ပါတယ်။", "He loves nature and a peaceful day."),
        ("သူ့ရဲ့ သူငယ်ချင်းတွေထဲမှာ လိပ်ပြာလေးတစ်ကောင်လည်း ပါပါတယ်။", "Among his friends is a little butterfly."),
    ]),
    ("The three rodents", "story", [
        ("ဒါပေမယ့် ငြိမ်းချမ်းတဲ့ မနက်ခင်းက မကြာခင် ပြောင်းလဲသွားပါတယ်။", "But the peaceful morning soon changes."),
        ("ကြွက်မျိုးနွယ်ကောင်သုံးကောင် ရောက်လာကြပါတယ်။", "Three rodents arrive."),
        ("သူတို့နာမည်တွေက Frank၊ Rinky နဲ့ Gamera ဖြစ်ပါတယ်။", "Their names are Frank, Rinky and Gamera."),
        ("Frank က အုပ်စုခေါင်းဆောင်ပါ။", "Frank is the leader."),
        ("သူတို့က ယုန်ကြီးကို စတင် စိတ်ဆိုးအောင် လုပ်ပါတယ်။", "They start to provoke the big rabbit."),
        ("ယုန်ကြီးကို အနိုင်ကျင့်ပြီး ရယ်မောကြပါတယ်။", "They bully the rabbit and laugh at him."),
        ("သူတို့ရဲ့ လုပ်ရပ်က ပိုပြီး ကြမ်းတမ်းလာပါတယ်။", "Their behavior becomes rougher."),
        ("နောက်ဆုံးမှာ လိပ်ပြာလေးကိုလည်း အန္တရာယ်ပြုကြပါတယ်။", "In the end they harm the little butterfly too."),
    ]),
    ("The revenge", "story", [
        ("ဒီအချိန်မှာ ယုန်ကြီးရဲ့ စိတ်သဘောထား ပြောင်းလဲသွားပါတယ်။", "At this moment the rabbit's mood changes."),
        ("သူက ငြိမ်းချမ်းတဲ့ ယုန်ကနေ ကြံစည်တတ်တဲ့ ယုန်ဖြစ်လာပါတယ်။", "He turns from a peaceful rabbit into a scheming one."),
        ("သူက ကိုယ်တိုင် ထောင်ချောက်တွေ ပြင်ဆင်ပါတယ်။", "He prepares traps himself."),
        ("ထောင်ချောက်တွေကို သဘာဝက ရတဲ့ ပစ္စည်းတွေနဲ့ လုပ်ပါတယ်။", "He builds the traps from natural objects."),
        ("သစ်ပင်၊ ကျောက်ခဲနဲ့ ကြိုးတွေကို အသုံးပြုပါတယ်။", "He uses trees, stones and ropes."),
        ("ဒီအပိုင်းတွေက ရယ်စရာကောင်းတဲ့ ပုံစံနဲ့ ပြထားပါတယ်။", "These parts are shown in a funny way."),
        ("ကြည့်ရှုသူတွေ ပြုံးမိကြပါလိမ့်မယ်။", "Viewers will find themselves smiling."),
        ("ကြွက်သုံးကောင်ကလည်း ဘာဖြစ်လာမလဲ မသိကြသေးပါဘူး။", "The three rodents do not yet know what is coming."),
    ]),
    ("The characters", "analysis", [
        ("ဇာတ်ကောင်တစ်ခုချင်းစီရဲ့ ပုံစံကို သေချာ ဖန်တီးထားပါတယ်။", "Each character was carefully designed."),
        ("ယုန်ကြီးက ကိုယ်ထည်ကြီးပြီး ချစ်စရာကောင်းပါတယ်။", "The rabbit is big and lovable."),
        ("ကြွက်သုံးကောင်ကတော့ သိသိသာသာ ကွဲပြားပါတယ်။", "The three rodents are clearly distinct."),
        ("တစ်ကောင်ချင်းစီမှာ ကိုယ်ပိုင်စရိုက် ရှိပါတယ်။", "Each one has its own personality."),
        ("အသံမပါဘဲ လှုပ်ရှားမှုနဲ့ပဲ စိတ်ခံစားမှုကို ပြထားပါတယ်။", "Feelings are shown through movement rather than speech."),
        ("ဒါကြောင့် ဘာသာစကားမရွေး နားလည်နိုင်ပါတယ်။", "So it can be understood in any language."),
        ("ဇာတ်လမ်းက ရိုးရှင်းပေမယ့် ထိရောက်ပါတယ်။", "The story is simple but effective."),
        ("ကလေးတွေနဲ့ လူကြီးတွေ နှစ်ဖက်စလုံး ကြည့်လို့ ရပါတယ်။", "Both children and adults can enjoy it."),
    ]),
    ("Open movies and licensing", "analysis", [
        ("Big Buck Bunny ကို Creative Commons လိုင်စင်နဲ့ ဖြန့်ချိထားပါတယ်။", "Big Buck Bunny is released under a Creative Commons license."),
        ("ဒီလိုင်စင်အရ မူရင်းဖန်တီးသူကို အသိအမှတ်ပြုရပါတယ်။", "Under this license the original creators must be credited."),
        ("အသိအမှတ်ပြုပြီး ပြန်လည် ဝေမျှနိုင်ပါတယ်။", "With credit it may be shared again."),
        ("ဒါကြောင့် ကျောင်းတွေနဲ့ ဖန်တီးသူတွေက ဒီရုပ်ရှင်ကို အသုံးပြုကြပါတယ်။", "That is why schools and creators use this film."),
        ("ဆော့ဖ်ဝဲ စမ်းသပ်ဖို့ ဥပမာအဖြစ်လည်း အသုံးများပါတယ်။", "It is also widely used as a test clip for software."),
        ("မူရင်းဖိုင်တွေကိုလည်း လွတ်လပ်စွာ ဒေါင်းလုဒ်လုပ်နိုင်ပါတယ်။", "The source files can also be downloaded freely."),
        ("ဒါက အခြား ကာတွန်းဖန်တီးသူတွေကို လေ့လာဖို့ အကူအညီပေးပါတယ်။", "That helps other animators to learn."),
        ("ဖွင့်လှစ်ထားတဲ့ ဖန်တီးမှုရဲ့ အားသာချက် ဖြစ်ပါတယ်။", "This is the strength of open creation."),
    ]),
    ("Legacy", "analysis", [
        ("ဒီရုပ်ရှင်ပြီးနောက် Blender ရဲ့ တတိယမြောက် ရုပ်ရှင်ကို ဆက်လက် ထုတ်လုပ်ခဲ့ပါတယ်။", "After this film Blender went on to make a third open movie."),
        ("အဲဒီရုပ်ရှင်က Sintel ဖြစ်ပါတယ်။", "That film is Sintel."),
        ("Big Buck Bunny က Blender ရဲ့ စွမ်းရည်ကို ပြသခဲ့ပါတယ်။", "Big Buck Bunny showed the ability of Blender."),
        ("အခမဲ့ ဆော့ဖ်ဝဲနဲ့ပါ အရည်အသွေးကောင်းတဲ့ ကာတွန်း လုပ်နိုင်တာကို သက်သေပြခဲ့ပါတယ်။", "It proved that quality animation can be made with free software."),
        ("ဒီနေ့ထိ ဖန်တီးသူအများကြီးက အားကျကြပါတယ်။", "To this day many creators look up to it."),
        ("အချိန်တိုပေမယ့် အမှတ်တရ ကျန်ခဲ့တဲ့ ရုပ်ရှင်လေးဖြစ်ပါတယ်။", "It is a short film that left a memory."),
        ("ဇာတ်ကြောင်းကို နှစ်သက်ရင် မူရင်းကို သွားကြည့်ပါ။", "If you liked the story, go and watch the original."),
        ("ဆက်လက်ကြည့်ရှုပေးတဲ့အတွက် ကျေးဇူးတင်ပါတယ်။", "Thank you for watching."),
    ]),
    ("Closing", "outro", [
        ("အခုဗီဒီယိုက အတိုချုပ် ပြောပြတာပဲ ဖြစ်ပါတယ်။", "This video was only a brief retelling."),
        ("မူရင်းရုပ်ရှင်ကို Blender က အခမဲ့ ဖြန့်ချိထားပါတယ်။", "The original film is distributed freely by Blender."),
        ("မူရင်းဖန်တီးသူတွေကို လေးစားပါတယ်။", "We respect the original creators."),
        ("နောက်ဗီဒီယိုမှာ ထပ်တွေ့ကြပါမယ်။", "See you in the next video."),
        ("YouTube နဲ့ Facebook မှာ ဆက်လက် ကြည့်ရှုပါ။", "Keep watching on YouTube and Facebook."),
        ("ကျေးဇူးတင်ပါတယ်။", "Thank you."),
    ]),
]


def sections():
    return [{"title": t, "kind": k, "items": [{"my": m, "en": e} for m, e in items]} for t, k, items in S]


def fake_llm(prompt, system="", json_mode=True):  # pragma: no cover - only used as a labelled test double
    raise RuntimeError("fixture mode never calls the AI provider; script text is supplied directly")
