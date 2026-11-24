import ast
from pathlib import Path


def test_telegram_help_documents_current_recap_voice_workflows():
    source = Path(__file__).with_name("bot.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    help_function = next(
        node for node in module.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "help_cmd"
    )
    help_text = "".join(
        node.value for node in ast.walk(help_function)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )

    required = (
        "/recapvoice [preset]",
        "/recapvoice3 [preset]",
        "/licensedownload <title>",
        "[PART 1]",
        "[PART 2]",
        "[PART 3]",
        "၄–၇ မိနစ်",
        "၁၅–၂၀ မိနစ်",
        "၄၆–၆၀ မိနစ်",
        "/platform youtube|facebook|tiktok",
        "/audioqa youtube|facebook|tiktok",
    )
    for item in required:
        assert item in help_text

    # The previous help text exposed outdated duration guidance and omitted
    # the measured recap voice commands.
    assert "TikTok: 1-3, 3-5, 4-7" not in help_text
    assert "Facebook: 3-5, 5-7, 8-10, 10-15, 46-60" not in help_text


def test_personal_voice_setup_tool_is_registered_and_explained():
    source = Path(__file__).with_name("bot.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    functions = {
        node.name: node for node in module.body
        if isinstance(node, ast.AsyncFunctionDef)
    }
    assert "myvoice_cmd" in functions
    assert "voiceclone_cmd" in functions
    assert 'CommandHandler("myvoice", myvoice_cmd)' in source
    assert '"/myvoice start|status|delete - ကိုယ်ပိုင်အသံ Setup Tool' in source
    assert "compatible GPU host" in ast.get_source_segment(source, functions["myvoice_cmd"])
    assert "VOICE_PROFILE_DB_PATH" in ast.get_source_segment(source, functions["myvoice_cmd"])
