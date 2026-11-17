import json
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import error_reporter


class ErrorReporterTests(unittest.TestCase):
    def setUp(self):
        error_reporter._last_sent.clear()
        error_reporter._in_flight.clear()

    def _raised_error(self):
        try:
            raise RuntimeError("PRIVATE TELEGRAM MESSAGE")
        except RuntimeError as exc:
            return exc

    def _success_response(self):
        response = MagicMock()
        response.__enter__.return_value.status = 201
        return response

    def test_disabled_without_token(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(error_reporter.report_error_to_github(RuntimeError("private text")))

    def test_report_body_excludes_exception_message_and_success_is_cooled_down(self):
        exc = self._raised_error()
        env = {
            "GITHUB_ERROR_REPORT_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "owner/repo",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "error_reporter.urlopen", return_value=self._success_response()
        ) as mocked:
            self.assertTrue(error_reporter.report_error_to_github(exc))
            request = mocked.call_args.args[0]
            payload = json.loads(request.data.decode("utf-8"))
            self.assertNotIn("PRIVATE TELEGRAM MESSAGE", json.dumps(payload))
            self.assertIn("RuntimeError", payload["title"])
            self.assertFalse(error_reporter.report_error_to_github(exc))
            self.assertEqual(mocked.call_count, 1)

    def test_request_failure_releases_reservation_for_retry(self):
        exc = self._raised_error()
        env = {
            "GITHUB_ERROR_REPORT_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "owner/repo",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "error_reporter.urlopen", side_effect=URLError("unavailable")
        ) as mocked:
            self.assertFalse(error_reporter.report_error_to_github(exc))
            self.assertFalse(error_reporter._in_flight)
            mocked.side_effect = None
            mocked.return_value = self._success_response()
            self.assertTrue(error_reporter.report_error_to_github(exc))
            self.assertEqual(mocked.call_count, 2)

    def test_in_flight_reservation_suppresses_concurrent_duplicate(self):
        self.assertTrue(error_reporter._claim_report("same"))
        self.assertFalse(error_reporter._claim_report("same"))
        error_reporter._finish_report("same", success=False)
        self.assertTrue(error_reporter._claim_report("same"))


if __name__ == "__main__":
    unittest.main()
