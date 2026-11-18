"""Daily free NEXORA animation recap research delivery, invoked by GitHub Actions."""
import json
import os
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from auto_research import search_movie_sources
from wikidata_metadata import fetch_wikidata_metadata, format_wikidata_metadata
from script_writer import generate_episode_selection_guide
from trend_sources import fetch_anime_trends, format_anime_trends
from pageview_trends import fetch_category_pageviews, format_category_pageviews

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


def build_daily_message(movie_title: str, research_text: str, metadata_text: str = "") -> str:
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
    return research_text + "\n\n" + metadata_section + plan + "\n\n" + generate_episode_selection_guide()


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
    metadata_report = format_wikidata_metadata(fetch_wikidata_metadata(movie))
    trend_report = format_anime_trends(fetch_anime_trends())
    pageview_report = format_category_pageviews(fetch_category_pageviews(TITLE_CATEGORIES))
    message = build_daily_message(movie, research, metadata_report) + "\n\n" + trend_report + "\n\n" + pageview_report
    send_telegram_message(token, chat_id, message)


if __name__ == "__main__":
    main()
