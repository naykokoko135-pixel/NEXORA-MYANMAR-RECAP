import unittest
import tempfile
from types import SimpleNamespace
import sys
from pathlib import Path
from unittest.mock import patch

from video_renderer import VideoRenderError, render_slideshow, validate_render_subtitles


class VideoRendererValidationTests(unittest.TestCase):
    def test_audio_duration_limit_supports_60_minute_longform_recap(self):
        from video_renderer import MAX_AUDIO_SECONDS
        self.assertEqual(MAX_AUDIO_SECONDS, 60 * 60)



    def test_concatenates_multiple_voice_tracks_in_order(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out.mp4"

            def fake_render(command, **kwargs):
                output.write_bytes(b"mp4")
                return type("Result", (), {"returncode": 0, "stderr": "", "stdout": ""})()

            fake_ffmpeg = SimpleNamespace(get_ffmpeg_exe=lambda: "ffmpeg")
            with patch.dict(sys.modules, {"imageio_ffmpeg": fake_ffmpeg}), \
                 patch("video_renderer._duration_seconds", side_effect=[2.0, 3.0]), \
                 patch("subprocess.run", side_effect=fake_render) as run:
                result = render_slideshow(
                    [("cover.jpg", b"image")],
                    [("narrator.mp3", b"voice1"), ("hero.wav", b"voice2")],
                    output,
                )

            self.assertEqual(result.read_bytes(), b"mp4")
            command = run.call_args.args[0]
            filter_graph = command[command.index("-filter_complex") + 1]
            self.assertIn("concat=n=2:v=0:a=1[aout]", filter_graph)
            self.assertIn("[1:a]aresample=44100", filter_graph)
            self.assertIn("[2:a]aresample=44100", command[command.index("-filter_complex") + 1])
            self.assertEqual(command[command.index("-t") + 1], "5.000")


    def test_platform_output_dimensions_are_selected(self):
        for platform, dimensions in {
            "youtube": "1280:720",
            "facebook": "864:1080",
            "tiktok": "720:1280",
        }.items():
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "out.mp4"

                def fake_render(command, **kwargs):
                    output.write_bytes(b"mp4")
                    return type("Result", (), {"returncode": 0, "stderr": "", "stdout": ""})()

                fake_ffmpeg = SimpleNamespace(get_ffmpeg_exe=lambda: "ffmpeg")
                with patch.dict(sys.modules, {"imageio_ffmpeg": fake_ffmpeg}), \
                     patch("video_renderer._duration_seconds", return_value=2.0), \
                     patch("subprocess.run", side_effect=fake_render) as run:
                    render_slideshow([("cover.jpg", b"image")], ("voice.mp3", b"audio"), output, platform=platform)

                vf = run.call_args.args[0][run.call_args.args[0].index("-vf") + 1]
                self.assertIn(f"scale={dimensions}", vf)
                self.assertIn("setsar=1", vf)

    def test_rejects_unknown_platform(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], ("voice.mp3", b"audio"), "out.mp4", platform="unknown")


    def test_embeds_burmese_srt_as_selectable_mp4_track(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out.mp4"

            def fake_render(command, **kwargs):
                output.write_bytes(b"mp4")
                return type("Result", (), {"returncode": 0, "stderr": "", "stdout": ""})()

            fake_ffmpeg = SimpleNamespace(get_ffmpeg_exe=lambda: "ffmpeg")
            subtitle_text = chr(10).join(["1", "00:00:00,000 --> 00:00:02,000", "မြန်မာစာတန်း", ""])
            with patch.dict(sys.modules, {"imageio_ffmpeg": fake_ffmpeg}), \
                 patch("video_renderer._duration_seconds", return_value=2.0), \
                 patch("subprocess.run", side_effect=fake_render) as run:
                render_slideshow(
                    [("cover.jpg", b"image")],
                    ("voice.mp3", b"audio"),
                    output,
                    platform="tiktok",
                    subtitle=("captions.srt", subtitle_text.encode("utf-8")),
                )

            command = run.call_args.args[0]
            self.assertIn("720:1280", command[command.index("-vf") + 1])
            self.assertIn("mov_text", command)
            self.assertIn("language=bur", command)
            self.assertIn("2:s:0", command)

    def test_rejects_invalid_srt_file(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow(
                [("cover.jpg", b"image")], ("voice.mp3", b"audio"), "out.mp4",
                subtitle=("captions.txt", b"not an srt"),
            )

    def test_rejects_non_utf8_srt(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow(
                [("cover.jpg", b"image")], ("voice.mp3", b"audio"), "out.mp4",
                subtitle=("captions.srt", bytes([255]) + b"-->"),
            )

    def test_rejects_empty_image_list(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([], ("voice.mp3", b"audio"), "out.mp4")

    def test_rejects_unsupported_image_type(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("clip.gif", b"image")], ("voice.mp3", b"audio"), "out.mp4")

    def test_rejects_unsupported_audio_type(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], ("voice.txt", b"audio"), "out.mp4")

    def test_rejects_empty_audio(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], ("voice.mp3", b""), "out.mp4")

    def test_rejects_empty_audio_track_list(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], [], "out.mp4")

    def test_rejects_unsupported_type_in_audio_track_list(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], [("hero.mp3", b"audio"), ("bad.txt", b"audio")], "out.mp4")

    def test_rejects_combined_audio_over_limit(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow(
                [("cover.jpg", b"image")],
                [("one.mp3", b"x" * (10 * 1024 * 1024)), ("two.mp3", b"x" * (10 * 1024 * 1024 + 1))],
                "out.mp4",
            )

    def test_rejects_more_than_twelve_audio_tracks(self):
        tracks = [(f"{i}.mp3", b"x") for i in range(13)]
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], tracks, "out.mp4")

    def test_rejects_more_than_twelve_images(self):
        images = [(f"{index}.jpg", b"image") for index in range(13)]
        with self.assertRaises(VideoRenderError):
            render_slideshow(images, ("voice.mp3", b"audio"), "out.mp4")


    def test_scene_timeline_pairs_each_image_with_its_audio_duration(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "timeline.mp4"

            def fake_render(command, **kwargs):
                output.write_bytes(b"mp4")
                return type("Result", (), {"returncode": 0, "stderr": "", "stdout": ""})()

            fake_ffmpeg = SimpleNamespace(get_ffmpeg_exe=lambda: "ffmpeg")
            with patch.dict(sys.modules, {"imageio_ffmpeg": fake_ffmpeg}), \
                 patch("video_renderer._duration_seconds", side_effect=[2.5, 4.0]), \
                 patch("subprocess.run", side_effect=fake_render) as run:
                from video_renderer import render_scene_timeline
                render_scene_timeline(
                    [
                        {"title": "Intro", "image": ("one.jpg", b"image1"), "audio": ("one.mp3", b"voice1")},
                        {"title": "Reveal", "image": ("two.jpg", b"image2"), "audio": ("two.mp3", b"voice2")},
                    ],
                    output,
                )

            command = run.call_args.args[0]
            self.assertEqual(command[command.index("-t") + 1], "6.500")
            concat_input = command[command.index("-i") + 1]
            self.assertTrue(concat_input.endswith("slides.txt"))

    def test_scene_timeline_requires_one_audio_per_image(self):
        from video_renderer import render_scene_timeline
        with self.assertRaises(VideoRenderError):
            render_scene_timeline(
                [{"title": "Only image", "image": ("one.jpg", b"image"), "audio": None}],
                "out.mp4",
            )



class AutomaticRenderSubtitleQATests(unittest.TestCase):
    def test_valid_srt_passes_when_timing_matches_measured_audio(self):
        srt = "1\\n00:00:00,000 --> 00:00:10,000\\nမြန်မာစာတန်း\\n"
        result = validate_render_subtitles(srt, 10.0)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["caption_count"], 1)

    def test_large_timing_drift_is_flagged_for_review_not_blocked(self):
        srt = "1\\n00:00:00,000 --> 00:00:10,000\\nမြန်မာစာတန်း\\n"
        result = validate_render_subtitles(srt, 30.0)
        self.assertEqual(result["status"], "REVIEW")
        self.assertGreater(result["difference_seconds"], result["tolerance_seconds"])

    def test_malformed_srt_is_rejected_before_render(self):
        with self.assertRaises(VideoRenderError):
            validate_render_subtitles("not an SRT", 10.0)

    def test_render_pipeline_runs_automatic_srt_qa(self):
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out.mp4"

            def fake_render(command, **kwargs):
                output.write_bytes(b"mp4")
                return type("Result", (), {"returncode": 0, "stderr": "", "stdout": ""})()

            fake_ffmpeg = SimpleNamespace(get_ffmpeg_exe=lambda: "ffmpeg")
            srt = "1\\n00:00:00,000 --> 00:00:02,000\\nမြန်မာစာတန်း\\n"
            with ExitStack() as stack:
                stack.enter_context(patch.dict(sys.modules, {"imageio_ffmpeg": fake_ffmpeg}))
                stack.enter_context(patch("video_renderer._duration_seconds", return_value=2.0))
                qa = stack.enter_context(patch("video_renderer.validate_render_subtitles", wraps=validate_render_subtitles))
                stack.enter_context(patch("subprocess.run", side_effect=fake_render))
                render_slideshow(
                    [("cover.jpg", b"image")],
                    ("voice.mp3", b"audio"),
                    output,
                    subtitle=("captions.srt", srt.encode("utf-8")),
                )
            qa.assert_called_once()


if __name__ == "__main__":
    unittest.main()
