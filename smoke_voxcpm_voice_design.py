"""Run a real optional VoxCPM2 Burmese voice-design smoke test locally.

Example:
    NEXORA_VOXCPM_ENABLED=1 python smoke_voxcpm_voice_design.py --voice story_female
"""
import argparse
import asyncio
from pathlib import Path
import wave

from voxcpm_voice_design import VOICE_DESIGNS, synthesize_designed_burmese_voice


DEFAULT_TEXT = "မင်္ဂလာပါ။ NEXORA မြန်မာဇာတ်လမ်းအသံ စမ်းသပ်မှု ဖြစ်ပါတယ်။"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate a short VoxCPM2 Burmese WAV sample.")
    parser.add_argument("--voice", choices=sorted(VOICE_DESIGNS), default="story_female")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Short Burmese text to synthesize.")
    parser.add_argument("--output", default="voxcpm_voice_design_smoke.wav")
    args = parser.parse_args(argv)

    try:
        audio = asyncio.run(synthesize_designed_burmese_voice(args.text, args.voice))
        output_path = Path(args.output)
        if output_path.suffix.lower() != ".wav":
            parser.error("--output must use a .wav extension")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio)
        with wave.open(str(output_path), "rb") as wav_file:
            duration = wav_file.getnframes() / wav_file.getframerate()
            print(
                f"Created {output_path} | voice={args.voice} | "
                f"sample_rate={wav_file.getframerate()} Hz | "
                f"channels={wav_file.getnchannels()} | duration={duration:.2f}s"
            )
        return 0
    except (RuntimeError, ValueError, OSError) as exc:
        parser.exit(1, f"VoxCPM2 smoke test failed: {exc}\\n")


if __name__ == "__main__":
    raise SystemExit(main())
