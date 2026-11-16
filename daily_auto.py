"""Daily free NEXORA research delivery, invoked by GitHub Actions."""
import json
import os
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from auto_research import search_movie_sources

MOVIE_ROTATION = [
    "Avatar", "Titanic", "Inception", "Interstellar", "Jurassic Park",
    "The Lion King", "The Dark Knight", "Frozen", "Coco", "Finding Nemo",
    "Harry Potter and the Philosopher's Stone", "The Matrix", "Gladiator",
    "The Lord of the Rings: The Fellowship of the Ring", "Toy Story",
    "Up", "WALL-E", "Spider-Man: Into the Spider-Verse", "The Avengers",
    "Iron Man", "Back to the Future", "The Truman Show", "The Green Mile",
    "Parasite", "Whiplash", "The Shawshank Redemption", "Joker",
    "Dune", "Kung Fu Panda", "How to Train Your Dragon",
]


def select_daily_movie(local_date: date) -> str:
    """Choose one stable title per local calendar day, cycling through the list."""
    return MOVIE_ROTATION[local_date.toordinal() % len(MOVIE_ROTATION)]


def build_daily_message(movie_title: str, research_text: str) -> str:
    """Append a three-part YouTube plan without inventing plot details."""
    plan = (
        "\n\n🎬 YOUTUBE — ၃ ပိုင်းခွဲ Recap အစီအစဉ်\n"
        f"ဇာတ်ကား: {movie_title}\n"
        "Part 1 — ဇာတ်လမ်းမိတ်ဆက်၊ နေရာ/အချိန်နောက်ခံ၊ အဓိကဇာတ်ကောင်များ "
        "(အတည်ပြုထားသော မှတ်စုများဖြင့် ဖြည့်ရန်)\n"
        "Part 2 — အဓိကပြဿနာ၊ ပဋိပက္ခနှင့် ဇာတ်လမ်းတိုးတက်မှု "
        "(ရင်းမြစ်နှင့်တိုက်စစ်ပြီး ဖြည့်ရန်)\n"
        "Part 3 — အထွတ်အထိပ်၊ အဆုံးသတ်နှင့် သုံးသပ်ချက် "
        "(ရုပ်ရှင်နှင့်တိုက်စစ်ပြီး ဖြည့်ရန်)\n\n"
        "မှတ်ချက်: ဤအပိုင်းများသည် အစီအစဉ်/worksheet သာဖြစ်ပြီး "
        "ဇာတ်ညွှန်းအပြည့် သို့မဟုတ် ဗီဒီယိုမဟုတ်ပါ။ မထုတ်ဝေမီ လူကိုယ်တိုင် စစ်ဆေးပါ။"
    )
    return research_text + plan


def split_telegram_text(text: str, limit: int = 3900) -> list[str]:
    """Split long messages safely below Telegram's message-size limit."""
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
