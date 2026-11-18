import unittest

from video_renderer import VideoRenderError, render_slideshow


class VideoRendererValidationTests(unittest.TestCase):
    def test_rejects_empty_image_list(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([], ("voice.mp3", b"audio"), "out.mp4")

    def test_rejects_unsupported_image_type(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("clip.gif", b"image")], ("voice.mp3", b"audio"), "out.mp4")

    def test_rejects_unsupported_audio_type(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], ("voice.txt", b"audio"), "out.mp4")

    def test_rejects_empty_audio(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], ("voice.mp3", b""), "out.mp4")

    def test_rejects_empty_audio_track_list(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], [], "out.mp4")

    def test_rejects_unsupported_type_in_audio_track_list(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], [("hero.mp3", b"audio"), ("bad.txt", b"audio")], "out.mp4")

    def test_rejects_combined_audio_over_limit(self):
        with self.assertRaises(VideoRenderError):
            render_slideshow(
                [("cover.jpg", b"image")],
                [("one.mp3", b"x" * (10 * 1024 * 1024)), ("two.mp3", b"x" * (10 * 1024 * 1024 + 1))],
                "out.mp4",
            )

    def test_rejects_more_than_twelve_audio_tracks(self):
        tracks = [(f"{i}.mp3", b"x") for i in range(13)]
        with self.assertRaises(VideoRenderError):
            render_slideshow([("cover.jpg", b"image")], tracks, "out.mp4")

    def test_rejects_more_than_twelve_images(self):
        images = [(f"{index}.jpg", b"image") for index in range(13)]
        with self.assertRaises(VideoRenderError):
            render_slideshow(images, ("voice.mp3", b"audio"), "out.mp4")


if __name__ == "__main__":
    unittest.main()
