import tempfile
import unittest
from pathlib import Path

from social_publishing import (
    PublishingPreflightError,
    platform_readiness,
    publishing_status,
    validate_publish_request,
)


class SocialPublishingReadinessTests(unittest.TestCase):
    def test_platforms_are_disabled_by_default(self):
        for platform in ("youtube", "facebook", "tiktok"):
            status = platform_readiness(platform, {})
            self.assertFalse(status["ready"])
            self.assertFalse(status["master_enabled"])
            self.assertFalse(status["platform_enabled"])

    def test_readiness_never_returns_secret_values(self):
        env = {
            "SOCIAL_PUBLISHING_ENABLED": "true",
            "YOUTUBE_PUBLISH_ENABLED": "true",
            "YOUTUBE_UPLOAD_CLIENT_ID": "client-id-secret",
            "YOUTUBE_UPLOAD_CLIENT_SECRET": "client-secret-value",
            "YOUTUBE_UPLOAD_REFRESH_TOKEN": "refresh-token-value",
        }
        status = platform_readiness("youtube", env)
        self.assertTrue(status["ready"])
        self.assertNotIn("client-secret-value", repr(status))
        self.assertNotIn("refresh-token-value", repr(status))

    def test_status_reports_each_platform_separately(self):
        status = publishing_status({})
        self.assertEqual(set(status), {"youtube", "facebook", "tiktok"})

    def test_rejects_missing_rights_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / "ready.mp4"
            video.write_bytes(b"mp4")
            with self.assertRaises(PublishingPreflightError):
                validate_publish_request(
                    "youtube", video, "Test", rights_confirmed=False,
                    human_approved=True, public_posting_confirmed=True,
                )

    def test_rejects_missing_human_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / "ready.mp4"
            video.write_bytes(b"mp4")
            with self.assertRaises(PublishingPreflightError):
                validate_publish_request(
                    "facebook", video, "Test", rights_confirmed=True,
                    human_approved=False, public_posting_confirmed=True,
                )

    def test_rejects_without_explicit_public_post_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / "ready.mp4"
            video.write_bytes(b"mp4")
            with self.assertRaises(PublishingPreflightError):
                validate_publish_request(
                    "tiktok", video, "Test", rights_confirmed=True,
                    human_approved=True, public_posting_confirmed=False,
                )

    def test_accepts_fully_approved_mp4(self):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / "ready.mp4"
            video.write_bytes(b"valid test bytes")
            result = validate_publish_request(
                "youtube", video, "Original recap", rights_confirmed=True,
                human_approved=True, public_posting_confirmed=True,
            )
            self.assertEqual(result, video)

    def test_rejects_non_mp4_and_empty_files(self):
        with tempfile.TemporaryDirectory() as temp:
            wrong = Path(temp) / "ready.mov"
            wrong.write_bytes(b"data")
            with self.assertRaises(PublishingPreflightError):
                validate_publish_request(
                    "youtube", wrong, "Test", rights_confirmed=True,
                    human_approved=True, public_posting_confirmed=True,
                )
            empty = Path(temp) / "empty.mp4"
            empty.write_bytes(b"")
            with self.assertRaises(PublishingPreflightError):
                validate_publish_request(
                    "youtube", empty, "Test", rights_confirmed=True,
                    human_approved=True, public_posting_confirmed=True,
                )


if __name__ == "__main__":
    unittest.main()
