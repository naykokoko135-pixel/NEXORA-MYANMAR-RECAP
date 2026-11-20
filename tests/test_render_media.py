import unittest

from render_media import classify_render_document


class RenderMediaClassificationTests(unittest.TestCase):
    def test_accepts_supported_audio_documents_case_insensitively(self):
        for name in ("voice.wav", "voice.MP3", "voice.m4a", "voice.OGG"):
            with self.subTest(name=name):
                self.assertEqual(classify_render_document(name), "audio")

    def test_accepts_srt_subtitles(self):
        self.assertEqual(classify_render_document("captions.srt"), "subtitle")

    def test_rejects_unrelated_documents(self):
        for name in ("notes.txt", "image.pdf", "", "no_extension"):
            with self.subTest(name=name):
                self.assertIsNone(classify_render_document(name))


if __name__ == "__main__":
    unittest.main()
