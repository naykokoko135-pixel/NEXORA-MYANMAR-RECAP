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
