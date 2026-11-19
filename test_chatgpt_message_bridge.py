import unittest
from pathlib import Path


class ChatGPTTelegramMessageBridgeTests(unittest.TestCase):
    def test_message_route_is_authenticated_and_private_destination_only(self):
        source = (Path(__file__).resolve().parent / "bot.py").read_text(encoding="utf-8")
        start = source.index('@web_app.post("/chatgpt/send-message")')
        end = source.index('@web_app.post("/chatgpt/command")', start)
        route = source[start:end]
        self.assertIn("_bridge_authorized(request)", route)
        self.assertIn("CHATGPT_BRIDGE_CHAT_ID", route)
        self.assertIn('payload.get("message")', route)
        self.assertIn("len(message) > 3500", route)
        self.assertIn("telegram_app.bot.send_message(", route)
        self.assertNotIn("payload.get(\"chat_id\")", route)

    def test_action_schema_exposes_direct_message_operation(self):
        spec = (Path(__file__).resolve().parent / "chatgpt_action_openapi.yaml").read_text(encoding="utf-8")
        self.assertIn("/chatgpt/send-message:", spec)
        self.assertIn("operationId: sendNexoraMessage", spec)
        self.assertIn("maxLength: 3500", spec)
        self.assertIn("X-Nexora-Bridge-Key", spec)


if __name__ == "__main__":
    unittest.main()
