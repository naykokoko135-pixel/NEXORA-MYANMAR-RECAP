import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class ChatGPTBridgeSchemaTests(unittest.TestCase):
    def test_openapi_command_enum_matches_bot_allowlist(self):
        bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
        schema = (ROOT / "chatgpt_action_openapi.yaml").read_text(encoding="utf-8")

        allowlist_match = re.search(
            r"BRIDGE_ALLOWED_COMMANDS\s*=\s*\{(?P<body>.*?)\n\}",
            bot_source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(allowlist_match)
        bot_commands = set(re.findall(r'"([a-z][a-z0-9_-]*)"', allowlist_match.group("body")))

        enum_match = re.search(
            r"^\s{18}enum:\n(?P<body>(?:^\s{20}- [a-z][a-z0-9_-]*\n?)+)",
            schema,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(enum_match)
        schema_commands = set(re.findall(r"- ([a-z][a-z0-9_-]*)", enum_match.group("body")))

        self.assertEqual(schema_commands, bot_commands)

    def test_openapi_documents_all_bridge_routes(self):
        schema = (ROOT / "chatgpt_action_openapi.yaml").read_text(encoding="utf-8")
        self.assertIn("/chatgpt/bridge-health:", schema)
        self.assertIn("/chatgpt/command:", schema)
        self.assertIn("/chatgpt/send-file:", schema)
        self.assertIn("operationId: sendNexoraFile", schema)
        self.assertIn("maxLength: 28000000", schema)
        self.assertIn("maximum decoded size 20 MB", schema)


if __name__ == "__main__":
    unittest.main()
