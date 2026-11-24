import io
import unittest
import wave

from recap_voice_clone_pipeline import build_estimated_srt_for_audio


def make_wav(seconds=5, sample_rate=8000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * seconds * sample_rate)
    return buffer.getvalue()


class RecapVoiceClonePipelineTests(unittest.TestCase):
    def test_srt_ends_at_real_wav_duration(self):
        srt = build_estimated_srt_for_audio("မင်္ဂလာပါ။ ဒီနေ့ ဇာတ်လမ်းကို ပြောပြပါမယ်။", make_wav(5))
        self.assertIn("00:00:05,000", srt)
        self.assertIn("မင်္ဂလာပါ", srt)

    def test_rejects_invalid_wav(self):
        with self.assertRaises(ValueError):
            build_estimated_srt_for_audio("စာသား", b"not a wav")

    def test_rejects_empty_script(self):
        with self.assertRaises(ValueError):
            build_estimated_srt_for_audio("", make_wav(5))


if __name__ == "__main__":
    unittest.main()
