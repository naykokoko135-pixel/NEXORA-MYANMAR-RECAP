import json
import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import daily_auto


class DailyRecapTriggerTests(unittest.TestCase):
    def test_trigger_is_optional_when_not_configured(self):
        with patch.dict(os.environ, {
            "NEXORA_DAILY_RECAP_URL": "",
            "NEXORA_DAILY_RECAP_TOKEN": "",
        }, clear=False):
            self.assertFalse(daily_auto.trigger_daily_recap(date(2026, 11, 23)))

    def test_rejects_incomplete_or_non_https_configuration(self):
        with patch.dict(os.environ, {
            "NEXORA_DAILY_RECAP_URL": "http://example.invalid",
            "NEXORA_DAILY_RECAP_TOKEN": "x" * 40,
        }, clear=False):
            with self.assertRaises(RuntimeError):
                daily_auto.trigger_daily_recap(date(2026, 11, 23))

    def test_posts_bangkok_date_to_authenticated_render_endpoint(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"accepted": true}'
        with patch.dict(os.environ, {
            "NEXORA_DAILY_RECAP_URL": "https://nexora.example",
            "NEXORA_DAILY_RECAP_TOKEN": "s" * 40,
        }, clear=False), patch.object(daily_auto, "urlopen", return_value=response) as opener:
            self.assertTrue(daily_auto.trigger_daily_recap(date(2026, 11, 23)))
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "https://nexora.example/internal/daily-recap")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("X-nexora-daily-token"), "s" * 40)
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"date": "2026-11-23"})
        opener.assert_called_once_with(request, timeout=25)


if __name__ == "__main__":
    unittest.main()
