import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

import bot


TOKEN = "test-daily-recap-trigger-token-0123456789"


class InternalDailyRecapTriggerTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_server_token_fails_closed(self):
        request = MagicMock()
        with patch.dict(os.environ, {"NEXORA_DAILY_RECAP_TOKEN": ""}), patch.object(
            bot, "telegram_app", MagicMock()
        ):
            with self.assertRaises(HTTPException) as raised:
                await bot.trigger_internal_daily_recap(request, x_nexora_daily_token=TOKEN)
        self.assertEqual(raised.exception.status_code, 503)

    async def test_wrong_token_is_unauthorized(self):
        request = MagicMock()
        with patch.dict(os.environ, {"NEXORA_DAILY_RECAP_TOKEN": TOKEN}), patch.object(
            bot, "telegram_app", MagicMock()
        ):
            with self.assertRaises(HTTPException) as raised:
                await bot.trigger_internal_daily_recap(request, x_nexora_daily_token="wrong-token")
        self.assertEqual(raised.exception.status_code, 401)

    async def test_invalid_chat_id_is_rejected(self):
        request = MagicMock()
        request.json = AsyncMock(return_value={"chat_id": "not-a-chat"})
        with patch.dict(os.environ, {"NEXORA_DAILY_RECAP_TOKEN": TOKEN}), patch.object(
            bot, "telegram_app", MagicMock()
        ), patch.object(bot, "daily_recap_task", None):
            with self.assertRaises(HTTPException) as raised:
                await bot.trigger_internal_daily_recap(request, x_nexora_daily_token=TOKEN)
        self.assertEqual(raised.exception.status_code, 400)

    async def test_valid_request_queues_background_job(self):
        request = MagicMock()
        request.json = AsyncMock(return_value={"chat_id": "123456789"})
        runner = AsyncMock()
        with patch.dict(os.environ, {"NEXORA_DAILY_RECAP_TOKEN": TOKEN}), patch.object(
            bot, "telegram_app", MagicMock()
        ), patch.object(bot, "_run_scheduled_daily_recap", runner), patch.object(
            bot, "daily_recap_task", None
        ):
            result = await bot.trigger_internal_daily_recap(request, x_nexora_daily_token=TOKEN)
            task = bot.daily_recap_task
            await task
        self.assertEqual(result["status"], "accepted")
        runner.assert_awaited_once_with(123456789)

    async def test_duplicate_active_job_is_rejected(self):
        request = MagicMock()
        request.json = AsyncMock(return_value={"chat_id": "123456789"})
        active = MagicMock()
        active.done.return_value = False
        with patch.dict(os.environ, {"NEXORA_DAILY_RECAP_TOKEN": TOKEN}), patch.object(
            bot, "telegram_app", MagicMock()
        ), patch.object(bot, "daily_recap_task", active):
            with self.assertRaises(HTTPException) as raised:
                await bot.trigger_internal_daily_recap(request, x_nexora_daily_token=TOKEN)
        self.assertEqual(raised.exception.status_code, 409)

    async def test_status_route_requires_token_and_returns_minimal_state(self):
        with patch.dict(os.environ, {"NEXORA_DAILY_RECAP_TOKEN": TOKEN}), patch.object(
            bot, "daily_recap_state", {"status": "running", "started_at": 123, "completed_at": None}
        ):
            with self.assertRaises(HTTPException) as raised:
                await bot.internal_daily_recap_status(x_nexora_daily_token="wrong")
            self.assertEqual(raised.exception.status_code, 401)
            result = await bot.internal_daily_recap_status(x_nexora_daily_token=TOKEN)
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["started_at"], 123)
        self.assertNotIn("chat_id", result)


if __name__ == "__main__":
    unittest.main()
