import unittest

from web_console import (
    SESSION_TTL_SECONDS,
    create_console_session,
    verify_console_session,
)


class WebConsoleSessionTests(unittest.TestCase):
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
