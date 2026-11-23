import tempfile
import unittest
from pathlib import Path

from internet_archive_pipeline import (
    InternetArchiveRenderError,
    download_internet_archive_source,
    render_internet_archive_narrated_preview,
)


class InternetArchivePipelineTests(unittest.TestCase):
    def test_rejects_cc_by_without_network_access(self):
        with tempfile.TemporaryDirectory() as temp:
            source = {
                "identifier": "open-film-123",
                "license_uri": "https://creativecommons.org/licenses/by/4.0/",
                "files": [{"name": "open-film.mp4", "size": 1000}],
            }
            with self.assertRaises(InternetArchiveRenderError):
                download_internet_archive_source(source, temp)

    def test_rejects_malformed_identifier(self):
        with tempfile.TemporaryDirectory() as temp:
            source = {
                "identifier": "../not-safe",
                "license_uri": "https://creativecommons.org/publicdomain/mark/1.0/",
                "files": [{"name": "open-film.mp4", "size": 1000}],
            }
            with self.assertRaises(InternetArchiveRenderError):
                download_internet_archive_source(source, temp)

    def test_rejects_non_video_file(self):
        with tempfile.TemporaryDirectory() as temp:
            source = {
                "identifier": "open-film-123",
                "license_uri": "https://creativecommons.org/publicdomain/mark/1.0/",
                "files": [{"name": "cover.jpg", "size": 1000}],
            }
            with self.assertRaises(InternetArchiveRenderError):
                download_internet_archive_source(source, temp)

    def test_preview_requires_valid_timestamped_srt(self):
        with tempfile.TemporaryDirectory() as temp:
            source = {
                "identifier": "open-film-123",
                "license_uri": "https://creativecommons.org/publicdomain/mark/1.0/",
                "files": [{"name": "open-film.mp4", "size": 1000}],
            }
            with self.assertRaises(InternetArchiveRenderError):
                render_internet_archive_narrated_preview(
                    source, ("narration.mp3", b"audio"), "no timestamps",
                    Path(temp) / "out.mp4", "tiktok",
                )


if __name__ == "__main__":
    unittest.main()
