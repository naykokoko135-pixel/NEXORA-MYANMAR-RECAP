import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

import bot


class HealthEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_returns_503_until_telegram_is_initialized(self):
        with patch.object(bot, "telegram_app", None):
            with self.assertRaises(HTTPException) as raised:
                await bot.health()

        self.assertEqual(raised.exception.status_code, 503)

    async def test_health_returns_ok_after_telegram_is_initialized(self):
        with patch.object(bot, "telegram_app", MagicMock()):
            result = await bot.health()

        self.assertEqual(result, {"status": "ok", "telegram": True})


if __name__ == "__main__":
    unittest.main()
