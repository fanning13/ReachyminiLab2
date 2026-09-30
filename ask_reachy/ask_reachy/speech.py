"""Fixed lines for the two-story session.

Both characteristics speak this same script. A session says the
introduction once, then two stories. Each story is one prompt, two
"What's next?" follow-ups, the continue question, and that story's
goodbye. The study then ends with one closing line.

Prompt order and which characteristic plays which prompt are shuffled
per session. The words are not.

Each line has a text sidecar and a WAV. Playback is refused if they
disagree. The WAVs were made once with macOS ``say`` (voice Samantha,
160 words per minute, 22050 Hz, mono, 16-bit). Do not regenerate them
mid-study.
"""

from __future__ import annotations

import random
import wave
from dataclasses import dataclass
from pathlib import Path

from ask_reachy.choreography import ENTHUSIASTIC_ENERGY, RESERVED_ENERGY

_ASSETS = Path(__file__).resolve().parent / "assets"


@dataclass(frozen=True)
class ScriptedLine:
    """One fixed utterance: a stable file key and the exact spoken words."""

    key: str
    text: str


@dataclass(frozen=True)
class Characteristic:
    """Nonverbal style. The spoken script does not depend on this."""

    name: str
    motion_energy: float


@dataclass(frozen=True)
class Prompt:
    key: str
    line: ScriptedLine


@dataclass(frozen=True)
class StorySlot:
    """One story in a session: a prompt paired with one characteristic."""

    prompt: Prompt
    characteristic: Characteristic


INTRO = ScriptedLine(
    "intro",
    "Hi there, I'm Reachy Mini, your storytelling companion. "
    "In this task, we will work together to write a story.",
)

PROMPT_A = Prompt(
    "A",
    ScriptedLine(
        "prompt_a",
        "It's fall in New York. You find a handwritten note tucked beneath "
        "a pile of fallen leaves. What happens next?",
    ),
)

PROMPT_B = Prompt(
    "B",
    ScriptedLine(
        "prompt_b",
        "It's fall in New York. While walking down a familiar street, you "
        "notice something that wasn't there yesterday. What happens next?",
    ),
)

WHATS_NEXT = ScriptedLine("whats_next", "That's interesting. What's next?")

CONTINUE_QUESTION = ScriptedLine(
    "continue_expanding",
    "Interesting story. Would you like to continue expanding it?",
)

# Spoken after the third story response. The first two follow-ups match.
STORY_FOLLOWUPS: tuple[ScriptedLine, ...] = (
    WHATS_NEXT,
    WHATS_NEXT,
    CONTINUE_QUESTION,
)

END_STORY = {
    1: ScriptedLine(
        "end_story_1",
        "Thank you for your participation. That's the end of Story 1.",
    ),
    2: ScriptedLine(
        "end_story_2",
        "Thank you for your participation. That's the end of Story 2.",
    ),
}

STUDY_CLOSING = ScriptedLine(
    "study_closing",
    "That conclude our study. Thank you so much for your participation.",
)

SHY = Characteristic("Shy", RESERVED_ENERGY)
CURIOUS = Characteristic("Curious", ENTHUSIASTIC_ENERGY)

ALL_LINES: tuple[ScriptedLine, ...] = (
    INTRO,
    PROMPT_A.line,
    PROMPT_B.line,
    WHATS_NEXT,
    CONTINUE_QUESTION,
    END_STORY[1],
    END_STORY[2],
    STUDY_CLOSING,
)


def plan_session(rng: random.Random) -> tuple[StorySlot, StorySlot]:
    """Shuffle prompt order and characteristic assignment independently.

    Every session uses both prompts and both characteristics. Which prompt
    is first, and which characteristic is paired with it, both vary.
    """
    prompts = [PROMPT_A, PROMPT_B]
    characteristics = [SHY, CURIOUS]
    rng.shuffle(prompts)
    rng.shuffle(characteristics)
    return (
        StorySlot(prompt=prompts[0], characteristic=characteristics[0]),
        StorySlot(prompt=prompts[1], characteristic=characteristics[1]),
    )


def text_path(line: ScriptedLine) -> Path:
    return _ASSETS / f"{line.key}.txt"


def wav_path(line: ScriptedLine) -> Path:
    return _ASSETS / f"{line.key}.wav"


def load_line(line: ScriptedLine) -> str:
    """Return ``line.text`` after checking the sidecar and the WAV."""
    path = text_path(line)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. The scripted line must sit beside its WAV."
        )
    recorded = path.read_text(encoding="utf-8").strip()
    if recorded != line.text:
        raise RuntimeError(
            f"{path.name} does not match the scripted line {line.text!r}. "
            "Refusing to speak audio that might not be this exact script."
        )
    audio = wav_path(line)
    if not audio.is_file():
        raise FileNotFoundError(
            f"Missing {audio}. Reachy speaks this file, not a generated sentence."
        )
    return line.text


def load_all_lines() -> None:
    """Fail before the robot moves if any recording is missing or mismatched."""
    for line in ALL_LINES:
        load_line(line)


def line_duration_s(line: ScriptedLine) -> float:
    """Duration of the checked-in recording for this line."""
    load_line(line)
    audio = wav_path(line)
    with wave.open(str(audio), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
    if rate <= 0:
        raise RuntimeError(f"Invalid sample rate in {audio}")
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


def play_line(reachy_mini, line: ScriptedLine) -> None:
    """Start this line's WAV on Reachy's speaker. Playback is non-blocking."""
    load_line(line)
    reachy_mini.media.play_sound(str(wav_path(line)))
