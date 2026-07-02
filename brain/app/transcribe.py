"""Voice note transcription with faster-whisper. Model loads lazily on first use."""
from __future__ import annotations

from . import config

_model = None


def transcribe(path: str) -> str:
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(config.WHISPER_MODEL, device="auto", compute_type="auto")
    segments, _info = _model.transcribe(path, language="da", vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()
