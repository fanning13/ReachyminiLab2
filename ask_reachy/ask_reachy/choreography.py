"""Authored gesture sequence for Ask Reachy.

Reserved (0.25) is the shy mood: antennas folded down, head lowered and pitched
down. Enthusiastic (0.90) bobs the head up and down and flicks the antennas
on a fast beat. Other energies scale the open sequence.

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

# Hardware stops. The shy pose uses these, not the conservative energetic caps.
HARDWARE_HEAD_DEG = 40.0
# Same antenna pose the SDK uses for sleep: both antennas folded down.
SHY_ANTENNAS_RAD = (-3.05, 3.05)


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
    z_m: float = 0.0


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

# Reserved (0.25) is the shy mood. Same eight names and durations as above.
# Positive pitch and a lowered head match the robot's sleep tuck (head down).
# Antennas stay at the folded-down pose for the whole sequence.
_SHY_RIGHT, _SHY_LEFT = SHY_ANTENNAS_RAD
_SHY_Z_M = -0.042
SHY_CHOREOGRAPHY: tuple[Gesture, ...] = (
    Gesture(
        "nod",
        0.70,
        pitch_deg=32.0,
        roll_deg=8.0,
        right_antenna_rad=_SHY_RIGHT,
        left_antenna_rad=_SHY_LEFT,
        z_m=_SHY_Z_M,
    ),
    Gesture(
        "antennas_lift",
        0.65,
        pitch_deg=34.0,
        roll_deg=10.0,
        right_antenna_rad=_SHY_RIGHT,
        left_antenna_rad=_SHY_LEFT,
        z_m=_SHY_Z_M,
    ),
    Gesture(
        "tilt_right",
        0.90,
        pitch_deg=34.0,
        roll_deg=14.0,
        yaw_deg=-8.0,
        right_antenna_rad=_SHY_RIGHT,
        left_antenna_rad=_SHY_LEFT,
        z_m=_SHY_Z_M,
    ),
    Gesture(
        "sway_left",
        0.90,
        pitch_deg=33.0,
        roll_deg=-6.0,
        right_antenna_rad=_SHY_RIGHT,
        left_antenna_rad=_SHY_LEFT,
        z_m=_SHY_Z_M,
    ),
    Gesture(
        "emphasis_nod",
        0.70,
        pitch_deg=36.0,
        roll_deg=6.0,
        right_antenna_rad=_SHY_RIGHT,
        left_antenna_rad=_SHY_LEFT,
        z_m=_SHY_Z_M,
    ),
    Gesture(
        "body_glance",
        0.95,
        pitch_deg=34.0,
        yaw_deg=-10.0,
        body_yaw_rad=-0.12,
        right_antenna_rad=_SHY_RIGHT,
        left_antenna_rad=_SHY_LEFT,
        z_m=_SHY_Z_M,
    ),
    Gesture(
        "antenna_wave",
        0.80,
        pitch_deg=34.0,
        roll_deg=8.0,
        right_antenna_rad=_SHY_RIGHT,
        left_antenna_rad=_SHY_LEFT,
        z_m=_SHY_Z_M,
    ),
    Gesture(
        "open_settle",
        0.80,
        pitch_deg=35.0,
        roll_deg=10.0,
        yaw_deg=-6.0,
        right_antenna_rad=_SHY_RIGHT,
        left_antenna_rad=_SHY_LEFT,
        z_m=_SHY_Z_M,
    ),
)

# Enthusiastic (0.90). Positive pitch is head-down (same axis as the shy tuck);
# negative pitch is head-up. Each beat is the shortest smooth goto (0.50 s),
# so the antennas reverse about twice a second for the length of the answer.
ENTHUSIASTIC_BEAT_S = 0.50
ENTHUSIASTIC_PITCH_DEG = 24.0
ENTHUSIASTIC_ANTENNA_RAD = 1.20
ENTHUSIASTIC_CHOREOGRAPHY: tuple[Gesture, ...] = tuple(
    Gesture(
        name="head_up" if i % 2 == 0 else "head_down",
        duration_s=ENTHUSIASTIC_BEAT_S,
        pitch_deg=-ENTHUSIASTIC_PITCH_DEG if i % 2 == 0 else ENTHUSIASTIC_PITCH_DEG,
        right_antenna_rad=ENTHUSIASTIC_ANTENNA_RAD
        if i % 2 == 0
        else -ENTHUSIASTIC_ANTENNA_RAD,
        left_antenna_rad=-ENTHUSIASTIC_ANTENNA_RAD
        if i % 2 == 0
        else ENTHUSIASTIC_ANTENNA_RAD,
    )
    for i in range(13)
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


def _check_shy(gesture: Gesture) -> None:
    for name, value in (
        ("roll_deg", gesture.roll_deg),
        ("pitch_deg", gesture.pitch_deg),
        ("yaw_deg", gesture.yaw_deg),
    ):
        if abs(value) > HARDWARE_HEAD_DEG:
            raise ValueError(
                f"{gesture.name} {name} {value} exceeds ±{HARDWARE_HEAD_DEG}"
            )
    if gesture.duration_s < 0.5:
        raise ValueError(
            f"{gesture.name} duration {gesture.duration_s} is below 0.5 s"
        )


def _check_enthusiastic(gesture: Gesture) -> None:
    if abs(gesture.pitch_deg) > HARDWARE_HEAD_DEG:
        raise ValueError(
            f"{gesture.name} pitch {gesture.pitch_deg} exceeds ±{HARDWARE_HEAD_DEG}"
        )
    if abs(gesture.right_antenna_rad) > 1.5 or abs(gesture.left_antenna_rad) > 1.5:
        raise ValueError(f"{gesture.name} antenna swing is past the lively range")
    if gesture.duration_s < 0.5:
        raise ValueError(
            f"{gesture.name} duration {gesture.duration_s} is below 0.5 s"
        )


def scaled_choreography(motion_energy: float) -> tuple[Gesture, ...]:
    """Return the gesture list for this energy.

    Reserved (0.25) plays the shy hiding sequence. Enthusiastic (0.90)
    bobs the head and flicks the antennas. Other values scale the open sequence.
    """
    energy = validate_energy(motion_energy)
    if abs(energy - RESERVED_ENERGY) < 1e-9:
        for gesture in SHY_CHOREOGRAPHY:
            _check_shy(gesture)
        return SHY_CHOREOGRAPHY
    if abs(energy - ENTHUSIASTIC_ENERGY) < 1e-9:
        for gesture in ENTHUSIASTIC_CHOREOGRAPHY:
            _check_enthusiastic(gesture)
        return ENTHUSIASTIC_CHOREOGRAPHY
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
