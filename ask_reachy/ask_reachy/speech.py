"""Fixed question and answer for Ask Reachy.

The answer string is the only words Reachy speaks. Nothing rewrites it.
Playback uses the WAV checked in next to this module so each run says the
same recording, not a freshly worded sentence.
"""

from __future__ import annotations

import wave
from pathlib import Path

# The participant asks this out loud. The app does not branch on the words.
EXPECTED_QUESTION = "Reachy, what do you like to do?"

# Identical across runs and across both motion conditions.
SCRIPTED_ANSWER = (
    "I like meeting people and answering questions. "
    "I listen first, then I speak while my head and antennas move with me."
)

_ASSETS = Path(__file__).resolve().parent / "assets"
ANSWER_TEXT_PATH = _ASSETS / "answer.txt"
ANSWER_WAV_PATH = _ASSETS / "answer.wav"


def load_scripted_answer() -> str:
    """Return the hardcoded answer after checking it matches the WAV sidecar."""
    if not ANSWER_TEXT_PATH.is_file():
        raise FileNotFoundError(
            f"Missing {ANSWER_TEXT_PATH}. The scripted answer text must sit beside the WAV."
        )
    recorded = ANSWER_TEXT_PATH.read_text(encoding="utf-8").strip()
    if recorded != SCRIPTED_ANSWER:
        raise RuntimeError(
            "answer.txt does not match SCRIPTED_ANSWER. "
            "Refusing to speak audio that might not be this exact script."
        )
    if not ANSWER_WAV_PATH.is_file():
        raise FileNotFoundError(
            f"Missing {ANSWER_WAV_PATH}. Reachy speaks this file, not a generated sentence."
        )
    return SCRIPTED_ANSWER


def answer_duration_s() -> float:
    """Duration of the checked-in answer recording."""
    load_scripted_answer()
    with wave.open(str(ANSWER_WAV_PATH), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
    if rate <= 0:
        raise RuntimeError(f"Invalid sample rate in {ANSWER_WAV_PATH}")
    return frames / float(rate)


def speech_backend_ready(reachy_mini) -> bool:
    """True when the SDK media layer can play a sound file."""
    media = getattr(reachy_mini, "media", None)
    if media is None:
        return False
    audio = getattr(media, "audio", None)
    if audio is None:
        return False
    try:
        rate = media.get_output_audio_samplerate()
    except Exception:
        return False
    return rate > 0


def play_scripted_answer(reachy_mini) -> None:
    """Start the fixed WAV on Reachy's speaker. Playback is non-blocking."""
    load_scripted_answer()
    reachy_mini.media.play_sound(str(ANSWER_WAV_PATH))
