import datetime as dt
import subprocess
from pathlib import Path

import pytest

from nexora import config, research, script, subs, state, render, qc


def test_platform_ranges():
    assert config.PLATFORMS["youtube"]["min"] == 46 and config.PLATFORMS["youtube"]["max"] == 60
    assert config.PLATFORMS["tiktok"]["min"] == 4 and config.PLATFORMS["tiktok"]["max"] == 7
    assert config.PLATFORMS["tiktok"]["h"] > config.PLATFORMS["tiktok"]["w"]


def test_category_rotation_distinct_per_day():
    d = dt.date(2026, 11, 24)
    firsts = [research.category_order(p, d)[0] for p in config.PLATFORM_ORDER]
    assert len(set(firsts)) == 3


def test_india_excluded_and_norm():
    assert state.norm("Spider-Man: Into!") == "spidermanInto".lower()
    assert "hi" in research.INDIA_LANGS


def test_split_sentences_and_chunks():
    assert script.split_sentences("က။ ခ။") == ["က။", "ခ။"]
    assert len(script.chunk_text("a\nb\nc\nd", 2)) == 2


def test_sections_parser():
    intro, s = research.split_sections("Intro\n== Plot ==\nstory here\n== Reception ==\ngood")
    assert intro == "Intro" and s["plot"] == "story here" and s["reception"] == "good"


def test_srt_roundtrip(tmp_path):
    tl = [dict(start=0, end=2, my="က", en="Hello there"), dict(start=2.2, end=4, my="ခ", en="x " * 60)]
    p = tmp_path / "a.srt"
    r = subs.write_srt(tl, p, "en")
    assert r["ok"] and r["cues"] == 2
    bad = tmp_path / "b.srt"
    bad.write_text("1\n00:00:00,000 --> 00:00:02,000\na\n\n2\n00:00:01,000 --> 00:00:03,000\nb\n", "utf-8")
    assert not subs.validate_srt(bad)["ok"]


def test_scenes_contiguous():
    tl = [dict(start=i * 3.0, end=i * 3.0 + 2.8, sec=i // 5, my="", en="") for i in range(12)]
    sc = render.make_scenes(tl, 10)
    assert all(abs(sc[i]["end"] - sc[i + 1]["start"]) < 1e-6 for i in range(len(sc) - 1))


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="no ffmpeg")
def test_render_smoke(tmp_path, monkeypatch):
    monkeypatch.setitem(config.PLATFORMS["tiktok"], "min", 0)
    tl = [dict(start=i * 2.0, end=i * 2.0 + 1.8, sec=i // 3, my="က", en=f"Line {i}") for i in range(9)]
    audio = tmp_path / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=300:d=18", str(audio)], check=True)
    srt = tmp_path / "en.srt"
    subs.write_srt(tl, srt, "en")
    out = tmp_path / "o.mp4"
    render.render(tl, audio, srt, "tiktok", "Test Title", tmp_path / "w", out)
    q = qc.check_mp4(out, "tiktok")
    assert out.exists() and q["duration_min"] > 0.2
    assert not any("H.264" in i or "resolution" in i or "no audio" in i for i in q["issues"]), q
