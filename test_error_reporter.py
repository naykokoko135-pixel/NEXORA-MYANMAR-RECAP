import os
import unittest
from unittest.mock import patch

import error_reporter


class ErrorReporterTests(unittest.TestCase):
    def setUp(self):
        error_reporter._last_sent.clear()

    def test_disabled_without_token(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(error_reporter.report_error_to_github(RuntimeError("private text")))

    def test_report_body_excludes_exception_message(self):
        try:
            raise RuntimeError("PRIVATE TELEGRAM MESSAGE")
        except RuntimeError as exc:
            summary = error_reporter._safe_frame_summary(exc)
        self.assertNotIn("PRIVATE TELEGRAM MESSAGE", summary)
        self.assertIn("test_report_body_excludes_exception_message", summary)

    def test_cooldown_suppresses_duplicate_fingerprint(self):
        self.assertTrue(error_reporter._claim_report("same"))
        self.assertFalse(error_reporter._claim_report("same"))


if __name__ == "__main__":
    unittest.main()
