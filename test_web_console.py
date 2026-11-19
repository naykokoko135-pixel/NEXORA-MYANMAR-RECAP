import unittest
from pathlib import Path

from web_console import (
    SESSION_TTL_SECONDS,
    create_console_session,
    verify_console_session,
)


class WebConsoleSessionTests(unittest.TestCase):
    def test_bot_module_compiles_and_console_routes_exist(self):
        source = (Path(__file__).resolve().parent / "bot.py").read_text(encoding="utf-8")
        compile(source, "bot.py", "exec")
        self.assertIn('@web_app.get("/console",', source)
        self.assertIn('@web_app.post("/console/command")', source)
        self.assertIn('NEXORA_CONSOLE_PASSWORD', source)

    def test_valid_session(self):
        token = create_console_session("a-secure-console-password", now=1000)
        self.assertTrue(verify_console_session(token, "a-secure-console-password", now=1001))

    def test_session_expires(self):
        token = create_console_session("a-secure-console-password", now=1000)
        self.assertFalse(
            verify_console_session(
                token, "a-secure-console-password", now=1000 + SESSION_TTL_SECONDS
            )
        )

    def test_wrong_password_and_tampered_token_fail(self):
        token = create_console_session("a-secure-console-password", now=1000)
        self.assertFalse(verify_console_session(token, "a-different-console-password", now=1001))
        self.assertFalse(verify_console_session(token + "tampered", "a-secure-console-password", now=1001))

    def test_invalid_secret_and_token_fail_closed(self):
        with self.assertRaises(ValueError):
            create_console_session("short", now=1000)
        self.assertFalse(verify_console_session("bad-token", "a-secure-console-password", now=1001))
        self.assertFalse(verify_console_session("1001.bad", "", now=1001))


if __name__ == "__main__":
    unittest.main()
