"""Turn the participant's audio into text for the researcher terminal.

Yes and no do not change what Reachy says next. Classification is only
so the terminal can record the continue answer. Empty or mixed answers
stay Unclear instead of being forced into Yes or No.
"""

from __future__ import annotations

import re
import threading
import wave
from pathlib import Path

import numpy as np

_YES = re.compile(
    r"\b(?:yes|yeah|yep|yup|sure|okay|ok|absolutely|definitely)\b",
    re.IGNORECASE,
)
_NO = re.compile(
    r"\b(?:no|nope|nah)\b|\bnot really\b|\bno thanks\b",
    re.IGNORECASE,
)

_model = None
_model_error = ""
_model_lock = threading.Lock()


def classify_yes_no(transcript: str) -> str:
    """Return Yes, No, or Unclear from the words the participant said."""
    text = transcript.replace("\u2019", "'").strip()
    if not text:
        return "Unclear"
    has_yes = _YES.search(text) is not None
    has_no = _NO.search(text) is not None
    if has_yes and not has_no:
        return "Yes"
    if has_no and not has_yes:
        return "No"
    return "Unclear"


def write_turn_wav(chunks: list[np.ndarray], sample_rate: int, path: Path) -> None:
    """Write one mono 16-bit WAV from the samples captured during a turn."""
    if not chunks:
        audio = np.zeros(0, dtype=np.float32)
    else:
        audio = np.concatenate([_mono_float(chunk) for chunk in chunks])
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate if sample_rate > 0 else 16000)
        handle.writeframes(pcm.tobytes())


def _mono_float(sample: np.ndarray) -> np.ndarray:
    audio = np.asarray(sample, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.reshape(-1, audio.shape[-1]).mean(axis=1)
    audio = audio.reshape(-1)
    if audio.size == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    if peak > 1.5:
        audio = audio / 32768.0
    return audio


def load_recognizer() -> str:
    """Load the local speech model. Return an error string, or empty on success.

    The model stays on this computer. A missing install does not stop the
    session: durations are still recorded and transcripts stay empty.
    """
    global _model, _model_error
    with _model_lock:
        if _model is not None:
            return ""
        if _model_error:
            return _model_error
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            _model_error = (
                "faster-whisper is not installed, so turns will not be transcribed."
            )
            return _model_error
        try:
            _model = WhisperModel("base.en", device="cpu", compute_type="int8")
        except Exception as exc:
            _model_error = f"Could not load the speech model: {exc}"
            return _model_error
    return ""


def transcribe_wav(path: Path) -> tuple[str, str]:
    """Return ``(transcript, error)``. Error is empty when transcription ran."""
    error = load_recognizer()
    if error:
        return "", error
    try:
        segments, _info = _model.transcribe(
            str(path),
            language="en",
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
    except Exception as exc:
        return "", f"Transcription failed: {exc}"
    return text, ""
