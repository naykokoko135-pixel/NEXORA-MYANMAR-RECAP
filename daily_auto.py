"""Daily free NEXORA animation recap research delivery, invoked by GitHub Actions."""
import json
import os
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from auto_research import search_movie_sources

# Broad, evergreen candidate rotation across the four requested animation categories.
# This is a curated catalogue, not a live popularity/trending ranking.
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
        # International animated films and series
        "Miraculous: Tales of Ladybug & Cat Noir", "Shaun the Sheep",
        "Klaus", "Motu Patlu", "Chhota Bheem",
    ],
    "Cartoon": [
        "Avatar: The Last Airbender", "The Amazing World of Gumball",
        "Adventure Time", "Gravity Falls", "Regular Show", "Steven Universe",
        "The Owl House", "Rick and Morty", "SpongeBob SquarePants",
        "The Powerpuff Girls", "Ben 10", "Teen Titans",
        # South Korean animation and web-animation candidates
        "Pororo the Little Penguin", "Larva", "Pucca",
        "The Haunted House: The Secret of the Ghost Ball",
        "Leafie, A Hen into the Wild",
    ],
    "Donghua": [
        "The King's Avatar", "Soul Land", "The Daily Life of the Immortal King",
        "Battle Through the Heavens", "Perfect World", "A Record of a Mortal's Journey to Immortality",
        "Fog Hill of Five Elements", "Link Click", "Heaven Official's Blessing",
        "The Legend of Hei", "Scissor Seven", "White Cat Legend",
    ],
}

# Verified country/region labels for selected additional international candidates.
# Unknown titles deliberately remain unlabelled until checked against reliable sources.
TITLE_REGIONS = {
    "Pororo the Little Penguin": "South Korea",
    "Larva": "South Korea",
    "Pucca": "South Korea",
    "The Haunted House: The Secret of the Ghost Ball": "South Korea",
    "Leafie, A Hen into the Wild": "South Korea",
    "Miraculous: Tales of Ladybug & Cat Noir": "France",
    "Shaun the Sheep": "United Kingdom",
    "Klaus": "Spain",
    "Motu Patlu": "India",
    "Chhota Bheem": "India",
}


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


def build_daily_message(movie_title: str, research_text: str) -> str:
    """Append clear part lengths for all three publishing platforms."""
    category = category_for_title(movie_title)
    plan = (
        "\n\n🎬 NEXORA — ANIMATION RECAP PLAN\n"
        f"အမျိုးအစား: {category}\n"
        f"နိုင်ငံ/ဒေသ: {region_for_title(movie_title)}\n"
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
        "နေ့စဉ်စာရင်းသည် အမျိုးအစား ၄ မျိုးပါ curated title rotation ဖြစ်ပြီး live trending/view-count ranking မဟုတ်ပါ။ "
        "လက်ရှိလူကြည့်များမှုကို သီးခြား trend source ဖြင့် စစ်ဆေးရမည်။ "
        "အချက်အလက်ကို မူရင်းနှင့်ပြန်စစ်ပြီး ကိုယ်ပိုင် commentary ထည့်ပါ။ "
        "အသုံးပြုခွင့်ရှိသော visual/audio ကိုသာ သုံးပါ။"
    )
    return research_text + plan


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
    movie = select_daily_movie(local_today)
    research = search_movie_sources(movie)
    send_telegram_message(token, chat_id, build_daily_message(movie, research))


if __name__ == "__main__":
    main()
