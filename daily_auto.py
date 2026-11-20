"""Daily free NEXORA animation recap research delivery, invoked by GitHub Actions."""
import json
import os
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from auto_research import search_movie_sources
from wikidata_metadata import (fetch_wikidata_metadata, format_wikidata_metadata,
                               format_wikidata_episode_guide)
from script_writer import generate_episode_selection_guide
from trend_sources import fetch_anime_trends, format_anime_trends
from pageview_trends import fetch_category_pageviews, format_category_pageviews
from tvmaze_series import fetch_series_episode_guide, format_series_episode_guide
from anilist_series import fetch_anilist_episode_guide, format_anilist_episode_guide
from myanmar_plot_research import fetch_burmese_plot_section, PlotResearchError
from english_plot_research import fetch_english_plot_section, EnglishPlotError

# Four animation categories with titles from multiple countries/regions.
# This curated rotation is not a live popularity or view-count ranking.
TITLE_CATEGORIES = {
    "Anime": [
        "Spirited Away", "Your Name", "Demon Slayer: Kimetsu no Yaiba",
        "Attack on Titan", "Jujutsu Kaisen", "One Piece", "Naruto",
        "Fullmetal Alchemist: Brotherhood", "Hunter x Hunter", "Death Note",
        "My Hero Academia", "Frieren: Beyond Journey's End", "Solo Leveling",
        "Chainsaw Man", "Haikyu!!", "Violet Evergarden", "Suzume",
        "A Silent Voice", "Howl's Moving Castle", "Princess Mononoke",
        "Weathering with You", "The Boy and the Heron", "Dragon Ball Z",
        "Bleach", "Mob Psycho 100", "Spy × Family", "Vinland Saga",
    ],
    "3D Animation": [
        "Spider-Man: Into the Spider-Verse", "Spider-Man: Across the Spider-Verse",
        "Puss in Boots: The Last Wish", "The Super Mario Bros. Movie",
        "The Incredibles", "Ratatouille", "WALL-E", "Up", "Toy Story",
        "How to Train Your Dragon", "Kung Fu Panda", "The Mitchells vs. the Machines",
        "Miraculous: Tales of Ladybug & Cat Noir", "Pororo the Little Penguin",
        "Shaun the Sheep", "Klaus",
        "The Little Prince", "The Summit of the Gods", "The Breadwinner",
        "The Secret of Kells", "The Song of the Sea", "The Wild Robot",
        "The Boy and the Beast", "Ne Zha", "White Snake",
        "The Legend of Sealed Book", "The King of Kings",
    ],
    "Cartoon": [
        "Avatar: The Last Airbender", "The Amazing World of Gumball",
        "Adventure Time", "Gravity Falls", "Regular Show", "Steven Universe",
        "The Owl House", "Rick and Morty", "SpongeBob SquarePants",
        "The Powerpuff Girls", "Ben 10", "Teen Titans",
        "Larva", "Pucca", "The Haunted House: The Secret of the Ghost Ball",
        "Leafie, A Hen into the Wild", "Masha and the Bear",
        "The Fixies", "Grizzy and the Lemmings", "Oggy and the Cockroaches",
        "The Amazing World of Gumball", "The Deep",
    ],
    "Donghua": [
        "The King's Avatar", "Soul Land", "The Daily Life of the Immortal King",
        "Battle Through the Heavens", "Perfect World",
        "A Record of a Mortal's Journey to Immortality",
        "Fog Hill of Five Elements", "Link Click", "Heaven Official's Blessing",
        "The Legend of Hei", "Scissor Seven", "White Cat Legend",
        "The Ravages of Time", "The Outcast", "Dragon Raja",
    ],
    "International Movies": [
        "Train to Busan", "Parasite", "The Wandering Earth", "The Raid",
        "Crouching Tiger, Hidden Dragon", "Ip Man", "The Platform",
        "Society of the Snow", "The Intouchables", "The Lives of Others",
        "Inception", "Interstellar", "Dune", "Knives Out",
        "The Dark Knight", "Extraction", "All Quiet on the Western Front",
        "The Grand Budapest Hotel", "The Pursuit of Happyness",
        "The Secret in Their Eyes",
    ],
}

# Country/region labels are supplied only for titles with well-established origins.
# Any title not listed remains explicitly marked for source verification.
TITLE_REGIONS = {
    "Spirited Away": "Japan", "Your Name": "Japan",
    "Demon Slayer: Kimetsu no Yaiba": "Japan", "Attack on Titan": "Japan",
    "Jujutsu Kaisen": "Japan", "One Piece": "Japan", "Naruto": "Japan",
    "Fullmetal Alchemist: Brotherhood": "Japan", "Hunter x Hunter": "Japan",
    "Death Note": "Japan", "My Hero Academia": "Japan",
    "Frieren: Beyond Journey's End": "Japan", "Solo Leveling": "Japan / South Korea-origin web novel",
    "Chainsaw Man": "Japan", "Haikyu!!": "Japan", "Violet Evergarden": "Japan",
    "Suzume": "Japan", "A Silent Voice": "Japan", "Howl's Moving Castle": "Japan",
    "Princess Mononoke": "Japan", "Weathering with You": "Japan",
    "The Boy and the Heron": "Japan", "Dragon Ball Z": "Japan",
    "Bleach": "Japan", "Mob Psycho 100": "Japan", "Spy × Family": "Japan",
    "Vinland Saga": "Japan",
    "Spider-Man: Into the Spider-Verse": "United States",
    "Spider-Man: Across the Spider-Verse": "United States",
    "Puss in Boots: The Last Wish": "United States",
    "The Super Mario Bros. Movie": "United States / Japan",
    "The Incredibles": "United States", "Ratatouille": "United States",
    "WALL-E": "United States", "Up": "United States", "Toy Story": "United States",
    "How to Train Your Dragon": "United States",
    "Kung Fu Panda": "United States",
    "The Mitchells vs. the Machines": "United States",
    "Miraculous: Tales of Ladybug & Cat Noir": "France",
    "Pororo the Little Penguin": "South Korea",
    "Shaun the Sheep": "United Kingdom", "Klaus": "Spain",
    "The Little Prince": "France",
    "The Summit of the Gods": "France / Luxembourg",
    "The Breadwinner": "Ireland / Canada / Luxembourg",
    "The Secret of Kells": "Ireland / France / Belgium",
    "The Song of the Sea": "Ireland / Denmark / Belgium / Luxembourg / France",
    "The Wild Robot": "United States",
    "The Boy and the Beast": "Japan", "Ne Zha": "China",
    "White Snake": "China", "The Legend of Sealed Book": "China",
    "The King of Kings": "South Korea / United States",
    "Larva": "South Korea", "Pucca": "South Korea",
    "The Haunted House: The Secret of the Ghost Ball": "South Korea",
    "Leafie, A Hen into the Wild": "South Korea",
    "Masha and the Bear": "Russia",
    "The Fixies": "Russia", "Grizzy and the Lemmings": "France",
    "Oggy and the Cockroaches": "France",
    "The Deep": "Australia / Canada",
    "The King's Avatar": "China", "Soul Land": "China",
    "The Daily Life of the Immortal King": "China",
    "Battle Through the Heavens": "China", "Perfect World": "China",
    "A Record of a Mortal's Journey to Immortality": "China",
    "Fog Hill of Five Elements": "China", "Link Click": "China",
    "Heaven Official's Blessing": "China", "The Legend of Hei": "China",
    "Scissor Seven": "China", "White Cat Legend": "China",
    "The Ravages of Time": "China", "The Outcast": "China",
    "Dragon Raja": "China",
    "Train to Busan": "South Korea", "Parasite": "South Korea",
    "The Wandering Earth": "China", "The Raid": "Indonesia",
    "Crouching Tiger, Hidden Dragon": "Taiwan / Hong Kong / United States / China",
    "Ip Man": "Hong Kong", "The Platform": "Spain",
    "Society of the Snow": "Spain / Uruguay", "The Intouchables": "France",
    "The Lives of Others": "Germany", "Inception": "United States / United Kingdom",
    "Interstellar": "United States / United Kingdom", "Dune": "United States / Canada",
    "Knives Out": "United States", "The Dark Knight": "United States / United Kingdom",
    "Extraction": "United States", "All Quiet on the Western Front": "Germany",
    "The Grand Budapest Hotel": "United States / Germany",
    "The Pursuit of Happyness": "United States",
    "The Secret in Their Eyes": "Argentina / Spain",
}



# Media format is deliberately separate from the five editorial categories.
# International Movies are live-action only; unknown formats remain unverified.
SERIES_TITLES = {
    "Demon Slayer: Kimetsu no Yaiba", "Attack on Titan", "Jujutsu Kaisen",
    "One Piece", "Naruto", "Fullmetal Alchemist: Brotherhood", "Hunter x Hunter",
    "Death Note", "My Hero Academia", "Frieren: Beyond Journey's End",
    "Solo Leveling", "Chainsaw Man", "Haikyu!!", "Violet Evergarden",
    "Dragon Ball Z", "Bleach", "Mob Psycho 100", "Spy × Family", "Vinland Saga",
    "Miraculous: Tales of Ladybug & Cat Noir", "Pororo the Little Penguin",
    "Shaun the Sheep", "Avatar: The Last Airbender", "The Amazing World of Gumball",
    "Adventure Time", "Gravity Falls", "Regular Show", "Steven Universe",
    "The Owl House", "Rick and Morty", "SpongeBob SquarePants",
    "The Powerpuff Girls", "Ben 10", "Teen Titans", "Larva", "Pucca",
    "The Haunted House: The Secret of the Ghost Ball", "Masha and the Bear",
    "The Fixies", "Grizzy and the Lemmings", "Oggy and the Cockroaches",
    "The Deep", "The King's Avatar", "Soul Land",
    "The Daily Life of the Immortal King", "Battle Through the Heavens",
    "Perfect World", "A Record of a Mortal's Journey to Immortality",
    "Fog Hill of Five Elements", "Link Click", "Heaven Official's Blessing",
    "Scissor Seven", "White Cat Legend", "The Ravages of Time", "The Outcast",
    "Dragon Raja",
}
ANIMATED_FILM_TITLES = {
    "Spirited Away", "Your Name", "Suzume", "A Silent Voice",
    "Howl's Moving Castle", "Princess Mononoke", "Weathering with You",
    "The Boy and the Heron", "Spider-Man: Into the Spider-Verse",
    "Spider-Man: Across the Spider-Verse", "Puss in Boots: The Last Wish",
    "The Super Mario Bros. Movie", "The Incredibles", "Ratatouille", "WALL-E",
    "Up", "Toy Story", "How to Train Your Dragon", "Kung Fu Panda",
    "The Mitchells vs. the Machines", "Klaus", "The Little Prince",
    "The Summit of the Gods", "The Breadwinner", "The Secret of Kells",
    "The Song of the Sea", "The Wild Robot", "The Boy and the Beast", "Ne Zha",
    "White Snake", "The Legend of Sealed Book", "The King of Kings",
    "Leafie, A Hen into the Wild", "The Legend of Hei",
}

def format_for_title(title: str) -> str:
    """Return a conservative media-format label without guessing unknown titles."""
    if title in TITLE_CATEGORIES["International Movies"]:
        return "Live-action Film"
    if title in SERIES_TITLES:
        return "Animated Series"
    if title in ANIMATED_FILM_TITLES:
        return "Animated Film"
    return "မီဒီယာပုံစံကို Official Source ဖြင့် စစ်ဆေးရန်"


def region_for_title(title: str) -> str:
    return TITLE_REGIONS.get(title, "မူရင်းနိုင်ငံ/ဒေသကို ရင်းမြစ်ဖြင့် စစ်ဆေးရန်")


# Keep the legacy name for existing imports and tests.
MOVIE_ROTATION = [title for titles in TITLE_CATEGORIES.values() for title in titles]


def category_for_title(title: str) -> str:
    for category, titles in TITLE_CATEGORIES.items():
        if title in titles:
            return category
    return "Animation"


def select_daily_movie(local_date: date) -> str:
    """Choose one stable candidate per local calendar day, cycling through categories."""
    return MOVIE_ROTATION[local_date.toordinal() % len(MOVIE_ROTATION)]


def build_daily_message(movie_title: str, research_text: str, metadata_text: str = "", series_text: str = "") -> str:
    """Append clear part lengths for all three publishing platforms."""
    category = category_for_title(movie_title)
    plan = (
        "\n\n🎬 NEXORA — RECAP PLAN\n"
        f"အမျိုးအစား: {category}\n"
        f"နိုင်ငံ/ဒေသ: {region_for_title(movie_title)}\n"
        f"မီဒီယာပုံစံ: {format_for_title(movie_title)}\n"
        f"ခေါင်းစဉ်: {movie_title}\n\n"
        "YOUTUBE — ၃ ပိုင်း၊ တစ်ပိုင်း ၈–၁၀ မိနစ် (စုစုပေါင်း ၂၄–၃၀ မိနစ်)\n"
        "Part 1: မိတ်ဆက်၊ နောက်ခံ၊ ဇာတ်ကောင်များနှင့် အစပြုဖြစ်ရပ်။\n"
        "Part 2: အဓိကပြဿနာ၊ turning points နှင့် ဇာတ်ကောင်ဆုံးဖြတ်ချက်များ။\n"
        "Part 3: Climax၊ သတ်မှတ်ထားသော season/film အဆုံးသတ်နှင့် သုံးသပ်ချက်။\n\n"
        "FACEBOOK — ၃ ပိုင်း၊ တစ်ပိုင်း ၃–၅ မိနစ် (စုစုပေါင်း ၉–၁၅ မိနစ်)\n"
        "Part 1: Hook + နောက်ခံ။ Part 2: ပဋိပက္ခ + အလှည့်အပြောင်း။ Part 3: ရလဒ် + သုံးသပ်ချက်။\n\n"
        "TIKTOK — ၃ ပိုင်း၊ တစ်ပိုင်း ၁–၃ မိနစ် (စုစုပေါင်း ၃–၉ မိနစ်)\n"
        "Part 1: Hook + စတင်ဖြစ်ရပ်။ Part 2: အဓိကပြဿနာ။ Part 3: အကျိုးဆက် + အမြင်။\n\n"
        "မှတ်ချက်: ဤစာသည် research lead နှင့် planning worksheet သာဖြစ်ပြီး ဇာတ်ညွှန်းအပြည့် သို့မဟုတ် ဗီဒီယိုမဟုတ်ပါ။ "
        "နေ့စဉ်စာရင်းသည် Anime၊ 3D Animation၊ Cartoon၊ Donghua နှင့် International Movies အမျိုးအစား ၅ မျိုးပါ curated international title rotation ဖြစ်ပြီး live trending/view-count ranking မဟုတ်ပါ။ Live-action ဇာတ်ကားများကို 3D Animation နှင့် မရောပါ။ အိန္ဒိယခေါင်းစဉ်များကို မထည့်ထားပါ။ "
        "နိုင်ငံ/ဒေသအမည်သည် မူရင်းထုတ်လုပ်မှု သို့မဟုတ် ပူးတွဲထုတ်လုပ်မှုကို ဆိုလိုနိုင်သည်။ "
        "လက်ရှိလူကြည့်များမှုကို သီးခြား trend source ဖြင့် စစ်ဆေးရမည်။ "
        "အချက်အလက်ကို မူရင်းနှင့်ပြန်စစ်ပြီး ကိုယ်ပိုင် commentary ထည့်ပါ။ "
        "အသုံးပြုခွင့်ရှိသော visual/audio ကိုသာ သုံးပါ။"
    )
    metadata_section = (metadata_text + "\n\n") if metadata_text else ""
    series_section = (series_text + "\n\n") if series_text else ""
    return research_text + "\n\n" + metadata_section + series_section + plan + "\n\n" + generate_episode_selection_guide()



def select_daily_platform_titles(local_date: date, pageview_result: dict | None = None) -> dict:
    """Choose three distinct editorial categories using the strongest available public attention signals."""
    pageview_result = pageview_result or {}
    category_data = pageview_result.get("categories") or {}
    rotation_offset = local_date.toordinal() % len(TITLE_CATEGORIES)
    ranked = []
    for index, (category, titles) in enumerate(TITLE_CATEGORIES.items()):
        items = category_data.get(category) or []
        valid_items = [
            item for item in items
            if item.get("title") in titles and int(item.get("recent_views") or 0) >= 0
        ]
        if valid_items:
            best = max(valid_items, key=lambda item: int(item.get("recent_views") or 0))
            ranked.append((
                int(best.get("recent_views") or 0),
                -((index - rotation_offset) % len(TITLE_CATEGORIES)),
                category,
                best.get("title"),
                best,
            ))
        else:
            fallback = titles[(local_date.toordinal() + index) % len(titles)]
            ranked.append((
                -1,
                -((index - rotation_offset) % len(TITLE_CATEGORIES)),
                category,
                fallback,
                {},
            ))
    ranked.sort(reverse=True)
    selected = {}
    for platform, entry in zip(("youtube", "facebook", "tiktok"), ranked[:3]):
        views, _, category, title, signal = entry
        selected[platform] = {
            "category": category,
            "title": title,
            "recent_wikipedia_views": views if views >= 0 else None,
            "pageview_change_pct": signal.get("change_pct"),
            "trend_source": (
                "Wikimedia English Wikipedia article pageviews"
                if views >= 0 else "Daily category rotation fallback (no pageview data)"
            ),
        }
    return selected


def _platform_cta(platform: str) -> str:
    youtube_url = os.environ.get("YOUTUBE_CHANNEL_URL", "").strip()
    facebook_url = os.environ.get("FACEBOOK_PAGE_URL", "").strip()
    if platform == "tiktok":
        links = " | ".join(x for x in (youtube_url, facebook_url) if x)
        destination = links or "Profile Bio ထဲက YouTube/Facebook link"
        return (
            "📣 CTA: ဒီအကြောင်းအရာရဲ့ နောက်ထပ် Recap တွေကို မလွတ်ချင်ရင် "
            f"YouTube ကို Subscribe၊ Facebook Page ကို Follow လုပ်ထားပါ။ {destination}"
        )
    if platform == "facebook":
        return (
            "📣 CTA: အရှည် Recap နဲ့ နောက်ထပ်ဇာတ်လမ်းတွေကို ကြည့်ဖို့ "
            + (f"YouTube မှာ Subscribe လုပ်ပါ — {youtube_url}" if youtube_url else "NEXORA YouTube Channel ကို Subscribe လုပ်ထားပါ။")
        )
    return (
        "📣 CTA: နေ့စဉ် Recap အသစ်တွေကို မလွတ်စေဖို့ Facebook Page ကို Follow လုပ်ထားပါ။"
        + (f" {facebook_url}" if facebook_url else "")
    )


def build_platform_daily_message(platform: str, item: dict, research_text: str,
                                 metadata_text: str = "", series_text: str = "") -> str:
    """Build a platform-specific daily production brief with a distinct title/category."""
    platform = str(platform or "").strip().lower()
    labels = {
        "youtube": ("YOUTUBE", "Long-form Recap", "၁၅–၂၀ မိနစ်", "၃ ပိုင်း၊ တစ်ပိုင်း ၅–၇ မိနစ်"),
        "facebook": ("FACEBOOK", "Mid-form Recap", "၁၀–၁၅ မိနစ်", "၃ ပိုင်း၊ တစ်ပိုင်း ၃–၅ မိနစ်"),
        "tiktok": ("TIKTOK", "Short-form Recap", "၁–၃ မိနစ်", "တစ်ပုဒ်တည်း၊ Hook → အတည်ပြုထားသော အချက် → CTA"),
    }
    if platform not in labels:
        raise ValueError("Unknown publishing platform.")
    label, format_name, duration, structure = labels[platform]
    title = item.get("title") or "ခေါင်းစဉ်မရရှိပါ"
    category = item.get("category") or category_for_title(title)
    views = item.get("recent_wikipedia_views")
    signal = (
        f"နောက်ဆုံး ၇ ရက် English Wikipedia article views: {int(views):,}"
        if views is not None else "လူကြိုက်များမှုဒေတာ: မရရှိပါ (နေ့စဉ် category rotation ဖြင့် ရွေးထားသည်)"
    )
    change = item.get("pageview_change_pct")
    if change is not None:
        signal += f" | ယခင် ၇ ရက်နှင့် {float(change):+.1f}%"
    sections = [
        f"🎬 NEXORA DAILY — {label}",
        f"နေ့စွဲ (ထိုင်းစံတော်ချိန်): {datetime.now(ZoneInfo('Asia/Bangkok')).date().isoformat()}",
        f"အမျိုးအစား: {category}",
        f"ခေါင်းစဉ်: {title}",
        f"နိုင်ငံ/ဒေသ: {region_for_title(title)}",
        f"မီဒီယာပုံစံ: {format_for_title(title)}",
        f"ရွေးချယ်မှုအချက်ပြ: {signal}",
        f"ရင်းမြစ်: {item.get('trend_source') or 'Daily category rotation'}",
        "",
        f"📺 {format_name} | ကြာချိန် {duration}",
        f"ဖွဲ့စည်းပုံ: {structure}",
        "တင်ဆက်ပုံ: ဒီ Platform အတွက် သီးခြား Hook၊ ဇာတ်ကြောင်းအစီအစဉ်၊ ခေါင်းစဉ်၊ Caption နှင့် Edit ဖြစ်ရမည်။",
        "ဇာတ်ကွက်ကို မခန့်မှန်းပါနှင့်။ Research Notes မလုံလောက်ပါက Worksheet အဖြစ်သာထားပါ။",
        "",
        "🔎 RESEARCH NOTES",
        research_text or "သက်ဆိုင်သော public research result မရရှိပါ။",
    ]
    if metadata_text:
        sections.extend(["", "🧾 IDENTITY / COUNTRY CROSS-CHECK", metadata_text])
    if series_text:
        sections.extend(["", "📚 SERIES / EPISODE GUIDE", series_text])
    if platform == "tiktok":
        sections.extend([
            "",
            "🎯 TikTok CTA (အသံနှင့် Caption နှစ်ခုလုံးတွင် ထည့်ရန်)",
            _platform_cta(platform),
            "CTA ကို Video အဆုံး ၃–၅ စက္ကန့်တွင် သဘာဝကျကျ ပြောပါ။ မမှန်သော link သို့မဟုတ် မရှိသော video ကို မညွှန်းပါနှင့်။",
        ])
    else:
        sections.extend(["", _platform_cta(platform)])
    sections.extend([
        "",
        "⚠️ သတိပြုရန်: Wikipedia article pageviews သည် ဆောင်းပါးဖတ်ရှုမှုသာဖြစ်ပြီး YouTube/Facebook/TikTok views မဟုတ်ပါ။ "
        "လူကြိုက်များမှုကို အတည်ပြုသည့် platform analytics မရှိလျှင် trend proxy ဟုသာ ဖော်ပြပါ။",
        "အသုံးပြုခွင့်ရှိသော visual/audio သို့မဟုတ် ကိုယ်ပိုင်ဖန်တီးထားသော visuals ကိုသာ သုံးပါ။ "
        "ဒီနေ့အတွက် အခြား Platform နှစ်ခုနှင့် ခေါင်းစဉ်/အမျိုးအစား မတူစေရပါ။",
    ])
    return "\n".join(sections)

def split_telegram_text(text: str, limit: int = 3900) -> list[str]:
    chunks = []
    remaining = text.strip()
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def send_telegram_message(token: str, chat_id: str, message: str) -> None:
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in split_telegram_text(message):
        payload = urlencode({"chat_id": chat_id, "text": chunk}).encode("utf-8")
        request = Request(endpoint, data=payload, method="POST")
        try:
            with urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise RuntimeError("Telegram message delivery failed.") from exc
        if not result.get("ok"):
            raise RuntimeError("Telegram rejected the message.")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as GitHub Actions secrets.")
    local_today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
    # Compare public attention signals across the five editorial categories.
    # Wikipedia pageviews are a proxy only, never represented as social-video views.
    pageview_result = fetch_category_pageviews(TITLE_CATEGORIES)
    selected = select_daily_platform_titles(local_today, pageview_result)
    messages = [
        "🌅 NEXORA — နေ့စဉ် Platform သုံးခုအတွက် သီးခြား Trend Research",
        f"နေ့စွဲ (ထိုင်းစံတော်ချိန်): {local_today.isoformat()}",
        "YouTube / Facebook / TikTok အတွက် category သုံးမျိုးနှင့် ခေါင်းစဉ်သုံးခုကို သီးခြားရွေးထားသည်။",
        "ရွေးချယ်မှုသည် နောက်ဆုံးရရှိသော English Wikipedia article pageviews ကို trend proxy အဖြစ်သုံးပြီး data မရှိပါက curated rotation သို့ ပြန်သုံးသည်။",
    ]
    for platform in ("youtube", "facebook", "tiktok"):
        item = selected[platform]
        title = item["title"]
        research = search_movie_sources(title)
        metadata = fetch_wikidata_metadata(title, expected_media_type=format_for_title(title))
        metadata_report = format_wikidata_metadata(metadata)

        # Add an actual Plot/Synopsis section only from the exact Wikidata
        # sitelink. Intro snippets and related list pages remain research leads,
        # never substitutes for a detailed plot source.
        if metadata.get("found"):
            plot_result = None
            mywiki_title = metadata.get("mywiki_title", "")
            enwiki_title = metadata.get("enwiki_title", "")
            if mywiki_title:
                try:
                    plot_result = fetch_burmese_plot_section(mywiki_title)
                except PlotResearchError:
                    plot_result = None
            if not plot_result and enwiki_title:
                try:
                    plot_result = fetch_english_plot_section(enwiki_title)
                except EnglishPlotError:
                    plot_result = None
            if plot_result:
                research += (
                    "\\n\\n📖 DETAILED PLOT RESEARCH (EXACT WIKIDATA SITELINK)\\n"
                    + "Section: " + str(plot_result.get("section", "Plot/Synopsis")) + "\\n"
                    + "Source type: " + str(plot_result.get("source_notice", "Community-edited plot section")) + "\\n"
                    + "Source: " + str(plot_result.get("source", "")) + "\\n"
                    + str(plot_result.get("plot_text", ""))[:6000]
                    + "\\n\\nသတိပြုရန်: ဤသည် Wikipedia လူထုတည်းဖြတ် Plot section ဖြစ်သည်။ Official source နှင့် ထပ်မံတိုက်စစ်ပါ။"
                )
            else:
                research += (
                    "\\n\\n⚠️ DETAILED PLOT SOURCE မရရှိပါ။ Intro snippet သာရှိသဖြင့် "
                    "ဇာတ်ညွှန်း/Full recap မထုတ်ဘဲ Worksheet အဖြစ်သာထားပါ။"
                )
        else:
            research += (
                "\\n\\n⚠️ Wikidata identity ကို media type နှင့် မခွဲနိုင်သေးပါ။ "
                "ဇာတ်ညွှန်း/Full recap မထုတ်ဘဲ Worksheet အဖြစ်သာထားပါ။"
            )

        series_report = ""
        if format_for_title(title) == "Animated Series":
            tvmaze_result = fetch_series_episode_guide(title)
            if tvmaze_result.get("found"):
                series_report = format_series_episode_guide(tvmaze_result)
            elif category_for_title(title) == "Anime":
                anilist_result = fetch_anilist_episode_guide(title)
                if anilist_result.get("found"):
                    series_report = format_anilist_episode_guide(anilist_result)
                else:
                    series_report = format_wikidata_episode_guide(metadata)
            else:
                series_report = format_wikidata_episode_guide(metadata)
        messages.extend(["", "━━━━━━━━━━━━━━━━━━", build_platform_daily_message(
            platform, item, research, metadata_report, series_report
        )])
    trend_report = format_anime_trends(fetch_anime_trends())
    pageview_report = format_category_pageviews(pageview_result)
    messages.extend(["", "━━━━━━━━━━━━━━━━━━", trend_report, "", pageview_report])
    send_telegram_message(token, chat_id, "\n".join(messages))


if __name__ == "__main__":
    main()
