from video_renderer import classify_render_document


def test_classify_supported_audio_documents():
    assert classify_render_document("narration.mp3") == "audio"
    assert classify_render_document("voice.WAV") == "audio"
    assert classify_render_document("track.m4a") == "audio"
    assert classify_render_document("voice.ogg") == "audio"


def test_classify_srt_document():
    assert classify_render_document("captions.srt") == "subtitle"
    assert classify_render_document("CAPTIONS.SRT") == "subtitle"


def test_reject_unsupported_document_types():
    assert classify_render_document("notes.txt") is None
    assert classify_render_document("movie.mp4") is None
    assert classify_render_document("") is None


def test_render_slideshow_creates_mp4_from_image_and_audio(tmp_path):
    import io
    import wave

    from PIL import Image
    from video_renderer import render_slideshow

    image_buffer = io.BytesIO()
    Image.new("RGB", (160, 90), (24, 48, 72)).save(image_buffer, format="PNG")

    audio_buffer = io.BytesIO()
    with wave.open(audio_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\\x00\\x00" * 8000)

    output = tmp_path / "render-smoke-test.mp4"
    result = render_slideshow(
        [("test.png", image_buffer.getvalue())],
        ("test.wav", audio_buffer.getvalue()),
        output,
        platform="youtube",
    )
    assert result.exists()
    assert result.stat().st_size > 0
