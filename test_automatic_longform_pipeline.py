import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automatic_longform_pipeline import render_licensed_longform_parts


SOURCE = {
    "title": "File:Open film.webm",
    "url": "https://upload.wikimedia.org/open-film.webm",
    "source_page": "https://commons.wikimedia.org/wiki/File:Open_film.webm",
    "license": "CC BY-SA 4.0",
    "mime": "video/webm",
    "size": 1000,
    "artist": "Creator",
}


class AutomaticLongformPipelineTests(unittest.TestCase):
    def test_downloads_renders_three_parts_and_removes_temporary_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seen = {}

            def fake_download(source, target):
                Path(target).write_bytes(b"licensed-video")
                seen["download_path"] = Path(target)
                return Path(target)

            def fake_render(source_path, audio, subtitles, output_dir, platform):
                self.assertTrue(Path(source_path).is_file())
                self.assertEqual(Path(source_path).read_bytes(), b"licensed-video")
                seen["render_args"] = (audio, subtitles, platform)
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                outputs = [Path(output_dir) / f"part_{i}.mp4" for i in (1, 2, 3)]
                for path in outputs:
                    path.write_bytes(b"mp4")
                return outputs

            with patch("automatic_longform_pipeline.download_licensed_source", side_effect=fake_download), patch(
                "automatic_longform_pipeline.render_three_part_longform", side_effect=fake_render
            ):
                outputs = render_licensed_longform_parts(
                    SOURCE, ("voice.mp3", b"audio"), ("captions.srt", b"srt"), root, "youtube"
                )

            self.assertEqual(len(outputs), 3)
            self.assertTrue(all(path.is_file() for path in outputs))
            self.assertEqual(
                seen["render_args"],
                (("voice.mp3", b"audio"), ("captions.srt", b"srt"), "youtube"),
            )
            self.assertFalse(seen["download_path"].exists())

    def test_download_failure_does_not_call_renderer_or_leave_partial_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def failed_download(source, target):
                Path(target).write_bytes(b"partial")
                raise RuntimeError("download failed")

            with patch("automatic_longform_pipeline.download_licensed_source", side_effect=failed_download), patch(
                "automatic_longform_pipeline.render_three_part_longform"
            ) as render:
                with self.assertRaisesRegex(RuntimeError, "download failed"):
                    render_licensed_longform_parts(
                        SOURCE, ("voice.mp3", b"audio"), ("captions.srt", b"srt"), root, "facebook"
                    )
            render.assert_not_called()
            self.assertEqual(list(root.glob(".nexora_source_*")), [])

    def test_rejects_tiktok_for_three_part_longform(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "YouTube/Facebook"):
                render_licensed_longform_parts(
                    SOURCE, ("voice.mp3", b"audio"), ("captions.srt", b"srt"), temp, "tiktok"
                )

    def test_requires_a_source_page(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "source page"):
                render_licensed_longform_parts(
                    {**SOURCE, "source_page": ""},
                    ("voice.mp3", b"audio"),
                    ("captions.srt", b"srt"),
                    temp,
                    "youtube",
                )


if __name__ == "__main__":
    unittest.main()
