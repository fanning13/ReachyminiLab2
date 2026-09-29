"""Authored gesture sequence for Ask Reachy.

The sequence, gesture count, order, and duration of every gesture are fixed.
``motion_energy`` (0.0 to 1.0) scales amplitude only. Because each gesture
keeps the same duration, average velocity scales with amplitude as well.

Full-scale angles (``motion_energy`` = 1.0) stay inside a conservative cap
so condition B (0.90) is still a modest first movement on a physical robot.
Hardware limits are wider: head pitch and roll ±40°, body yaw ±160°.
"""

from __future__ import annotations

from dataclasses import dataclass

# Study conditions. The spoken script does not change between them.
RESERVED_ENERGY = 0.25
ENTHUSIASTIC_ENERGY = 0.90

# Identical start and end pose: head centered, antennas at 0 rad, body yaw 0.
# This is mathematical neutral. The SDK's wake pose uses a ±10° antenna offset
# to reduce buzzing; do not switch to that offset unless start and end both use it.
NEUTRAL_ANTENNAS_RAD = (0.0, 0.0)
NEUTRAL_BODY_YAW_RAD = 0.0
NEUTRAL_GOTO_DURATION_S = 1.2

# Caps for the authored full-scale pose. Scaled motion is always smaller.
MAX_HEAD_DEG = 18.0
MAX_ANTENNA_RAD = 0.50
MAX_BODY_YAW_RAD = 0.20


@dataclass(frozen=True)
class Gesture:
    """One absolute pose in the choreography, at full scale (energy = 1)."""

    name: str
    duration_s: float
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    right_antenna_rad: float = 0.0
    left_antenna_rad: float = 0.0
    body_yaw_rad: float = 0.0


# Eight gestures. Durations sum to 6.40 s and never depend on motion_energy.
# Antenna order matches the SDK: [right, left], radians.
CHOREOGRAPHY: tuple[Gesture, ...] = (
    Gesture("nod", 0.70, pitch_deg=-12.0),
    Gesture(
        "antennas_lift",
        0.65,
        right_antenna_rad=0.40,
        left_antenna_rad=-0.40,
    ),
    Gesture("tilt_right", 0.90, roll_deg=14.0, yaw_deg=8.0),
    Gesture(
        "sway_left",
        0.90,
        roll_deg=-14.0,
        right_antenna_rad=-0.35,
        left_antenna_rad=0.35,
    ),
    Gesture(
        "emphasis_nod",
        0.70,
        pitch_deg=-14.0,
        right_antenna_rad=0.25,
        left_antenna_rad=-0.25,
    ),
    Gesture("body_glance", 0.95, yaw_deg=8.0, body_yaw_rad=0.15),
    Gesture(
        "antenna_wave",
        0.80,
        roll_deg=6.0,
        right_antenna_rad=-0.40,
        left_antenna_rad=0.40,
    ),
    Gesture(
        "open_settle",
        0.80,
        pitch_deg=8.0,
        right_antenna_rad=0.20,
        left_antenna_rad=-0.20,
    ),
)


def condition_label(motion_energy: float) -> str:
    """Map the two study values to their labels. Any other value is Custom."""
    rounded = round(float(motion_energy), 2)
    if abs(rounded - RESERVED_ENERGY) < 1e-9:
        return "Reserved"
    if abs(rounded - ENTHUSIASTIC_ENERGY) < 1e-9:
        return "Enthusiastic"
    return "Custom"


def validate_energy(motion_energy: float) -> float:
    """Return motion_energy rounded to two decimals, or raise ValueError."""
    rounded = round(float(motion_energy), 2)
    if rounded < 0.0 or rounded > 1.0:
        raise ValueError(
            f"motion_energy must be between 0.0 and 1.0, got {motion_energy}"
        )
    return rounded


def _check_caps(gesture: Gesture) -> None:
    for name, value in (
        ("roll_deg", gesture.roll_deg),
        ("pitch_deg", gesture.pitch_deg),
        ("yaw_deg", gesture.yaw_deg),
    ):
        if abs(value) > MAX_HEAD_DEG:
            raise ValueError(f"{gesture.name} {name} {value} exceeds ±{MAX_HEAD_DEG}")
    for name, value in (
        ("right_antenna_rad", gesture.right_antenna_rad),
        ("left_antenna_rad", gesture.left_antenna_rad),
    ):
        if abs(value) > MAX_ANTENNA_RAD:
            raise ValueError(
                f"{gesture.name} {name} {value} exceeds ±{MAX_ANTENNA_RAD}"
            )
    if abs(gesture.body_yaw_rad) > MAX_BODY_YAW_RAD:
        raise ValueError(
            f"{gesture.name} body_yaw_rad {gesture.body_yaw_rad} exceeds ±{MAX_BODY_YAW_RAD}"
        )
    if gesture.duration_s < 0.5:
        raise ValueError(
            f"{gesture.name} duration {gesture.duration_s} is below 0.5 s"
        )


def scaled_choreography(motion_energy: float) -> tuple[Gesture, ...]:
    """Return the same gestures with amplitudes multiplied by motion_energy.

    Names, order, count, and ``duration_s`` are copied unchanged.
    """
    energy = validate_energy(motion_energy)
    scaled: list[Gesture] = []
    for gesture in CHOREOGRAPHY:
        _check_caps(gesture)
        scaled.append(
            Gesture(
                name=gesture.name,
                duration_s=gesture.duration_s,
                roll_deg=gesture.roll_deg * energy,
                pitch_deg=gesture.pitch_deg * energy,
                yaw_deg=gesture.yaw_deg * energy,
                right_antenna_rad=gesture.right_antenna_rad * energy,
                left_antenna_rad=gesture.left_antenna_rad * energy,
                body_yaw_rad=gesture.body_yaw_rad * energy,
            )
        )
    return tuple(scaled)


def choreography_duration_s() -> float:
    """Total authored duration. Independent of motion_energy."""
    return sum(gesture.duration_s for gesture in CHOREOGRAPHY)
