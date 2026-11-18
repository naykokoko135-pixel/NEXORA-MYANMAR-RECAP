import unittest
import tempfile
from types import SimpleNamespace
import sys
from pathlib import Path
from unittest.mock import patch

from video_renderer import VideoRenderError, render_slideshow


class VideoRendererValidationTests(unittest.TestCase):

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
            self.assertIn("concat=n=2:v=0:a=1[aout]", command)
            self.assertIn("[1:a]aresample=44100", command[command.index("-filter_complex") + 1])
            self.assertIn("[2:a]aresample=44100", command[command.index("-filter_complex") + 1])
            self.assertEqual(command[command.index("-t") + 1], "5.000")

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


if __name__ == "__main__":
    unittest.main()
