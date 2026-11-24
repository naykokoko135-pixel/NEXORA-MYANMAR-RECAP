"""Daily: pick 3 distinct titles (one per platform), save, emit GitHub matrix. Idempotent per date."""
import datetime as dt
import json
import os
import sys

from . import config, publish, research, state


def main():
    date = dt.date.today().isoformat()
    picks = state.load_daily(date)
    if picks:
        print("reusing picks for", date)
    else:
        picks = research.pick_daily()
        state.save_daily(date, picks)
        for p, r in picks.items():
            state.mark_used(r["title"], p, date, r["category"])
    lines = [f"📅 {date} Daily picks"] + [f"• {p}: {r['title']} ({r['year']}) [{r['category']}]" for p, r in picks.items()]
    publish.tg("\n".join(lines))
    out = os.getenv("GITHUB_OUTPUT")
    matrix = json.dumps({"platform": list(picks)})
    if out:
        with open(out, "a") as f:
            f.write(f"matrix={matrix}\ndate={date}\n")
    print(matrix)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        publish.tg(f"❌ Daily research failed: {e}")
        sys.exit(1)
