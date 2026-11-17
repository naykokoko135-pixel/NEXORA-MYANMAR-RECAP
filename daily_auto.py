"""Daily free NEXORA anime research delivery, invoked by GitHub Actions."""
import json
import os
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from auto_research import search_movie_sources

# Anime films and series. Wikipedia results are research leads only; verify details.
# Keep the legacy constant name so existing tests/imports remain compatible.
MOVIE_ROTATION = [
    "Spirited Away", "Your Name", "Demon Slayer: Kimetsu no Yaiba",
    "Attack on Titan", "Jujutsu Kaisen", "One Piece", "Naruto",
    "Fullmetal Alchemist: Brotherhood", "Hunter x Hunter", "Death Note",
    "My Hero Academia", "Frieren: Beyond Journey's End", "Solo Leveling",
    "Chainsaw Man", "Haikyu!!", "Violet Evergarden", "Suzume",
    "A Silent Voice", "Howl's Moving Castle", "Princess Mononoke",
    "Weathering with You", "The Boy and the Heron", "Dragon Ball Z",
    "Bleach", "Mob Psycho 100", "Spy × Family", "Vinland Saga",
    "Re:Zero − Starting Life in Another World", "The Apothecary Diaries",
    "The Seven Deadly Sins",
]


def select_daily_movie(local_date: date) -> str:
    """Choose one stable anime title per local calendar day, cycling through the list."""
    return MOVIE_ROTATION[local_date.toordinal() % len(MOVIE_ROTATION)]


def build_daily_message(movie_title: str, research_text: str) -> str:
    """Append a three-part YouTube anime recap plan without inventing plot details."""
    plan = (
        "\n\n🎬 NEXORA ANIME — YOUTUBE ၃ ပိုင်းခွဲ Recap အစီအစဉ်\n"
        f"Anime: {movie_title}\n"
        "Part 1 — Anime မိတ်ဆက်၊ ကမ္ဘာ/နောက်ခံ၊ အဓိကဇာတ်ကောင်များ "
        "(အတည်ပြုထားသော မှတ်စုများဖြင့် ဖြည့်ရန်)\n"
        "Part 2 — အဓိကပဋိပက္ခ၊ ဇာတ်ကောင်ဖွံ့ဖြိုးမှုနှင့် အရေးကြီး turning points "
        "(ရင်းမြစ်နှင့်တိုက်စစ်ပြီး ဖြည့်ရန်)\n"
        "Part 3 — အထွတ်အထိပ်၊ season/film အဆုံးသတ်နှင့် ကိုယ်ပိုင်သုံးသပ်ချက် "
        "(ကြည့်ရှုထားသော အပိုင်းအကန့်အသတ်ကို ရှင်းလင်းဖော်ပြရန်)\n\n"
        "မှတ်ချက်: ဤအပိုင်းများသည် worksheet သာဖြစ်ပြီး ဇာတ်ညွှန်းအပြည့် သို့မဟုတ် ဗီဒီယိုမဟုတ်ပါ။ "
        "Wikipedia ရလဒ်များကို research lead အဖြစ်သာယူပါ။ မထုတ်ဝေမီ အချက်အလက်နှင့် "
        "အသုံးပြုခွင့်ရှိသော Visual/Audio များကို လူကိုယ်တိုင် စစ်ဆေးပါ။"
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
