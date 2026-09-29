"""Ask Reachy: one spoken answer, two movement energies.

Listening follows the conversation app's microphone path (record a chunk,
decide the person has finished). Movement follows coding_lab's style: a
fixed list of ``goto_target`` poses. The answer text never comes from a model.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np
from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.io.protocol import StopMoveCmd
from reachy_mini.utils import create_head_pose

from ask_reachy.choreography import (
    NEUTRAL_ANTENNAS_RAD,
    NEUTRAL_BODY_YAW_RAD,
    NEUTRAL_GOTO_DURATION_S,
    condition_label,
    scaled_choreography,
    validate_energy,
)
from ask_reachy.run_log import DEFAULT_LOG_PATH, iso_now, write_run_record
from ask_reachy.speech import (
    ANSWER_WAV_PATH,
    EXPECTED_QUESTION,
    SCRIPTED_ANSWER,
    answer_duration_s,
    play_scripted_answer,
    speech_backend_ready,
)

# Speech onset / end. Tuned for a close speaker, not a noisy room.
ONSET_RMS = 0.02
END_SILENCE_S = 0.8
MIN_SPEECH_S = 0.35


class OperatorStop(Exception):
    """The operator asked the trial to stop. Reachy still returns to neutral."""


class AskReachy(ReachyMiniApp):
    """Spoken question, scripted answer, energy-scaled choreography."""

    # Terminal study app. A settings page could change a trial, so it stays off.
    custom_app_url: str | None = None
    dont_start_webserver: bool = True

    def __init__(
        self,
        motion_energy: float,
        simulate_question: bool = False,
        listen_timeout_s: float = 45.0,
        log_path: Path | None = None,
        started_at: str | None = None,
        daemon_port: int = 8000,
    ) -> None:
        super().__init__()
        self.motion_energy = validate_energy(motion_energy)
        self.condition = condition_label(self.motion_energy)
        self.simulate_question = simulate_question
        self.listen_timeout_s = listen_timeout_s
        self.log_path = log_path or DEFAULT_LOG_PATH
        self.started_at = started_at or iso_now()
        self.daemon_port = daemon_port
        self._log_written = False
        self._cleaning_up = False
        self._status = "error"
        self._error = ""
        self._speech_played = False
        self._question_heard = False
        self._neutral_error_deg: float | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        """Run one trial, then return to the same neutral pose."""
        self._install_stop_handler(stop_event)
        try:
            self._print_startup()
            self._prepare_robot(reachy_mini)
            self._goto_neutral(reachy_mini, stop_event)
            self._listen(reachy_mini, stop_event)
            self._speak_and_move(reachy_mini, stop_event)
            self._status = "completed"
        except OperatorStop:
            self._status = "stopped"
            print("Stop requested. Returning Reachy to neutral.")
        except KeyboardInterrupt:
            self._status = "stopped"
            print("Ctrl+C. Returning Reachy to neutral.")
        except Exception:
            self._status = "error"
            self._error = traceback.format_exc()
            print(self._error, file=sys.stderr)
        finally:
            self._cleaning_up = True
            cleanup_error = self._return_to_neutral(reachy_mini)
            if cleanup_error and self._status == "completed":
                self._status = "error"
            if cleanup_error:
                self._error = (
                    f"{self._error}\n{cleanup_error}".strip()
                    if self._error
                    else cleanup_error
                )
            self._write_log()

    def record_connection_failure(self, exc: BaseException) -> None:
        """Log a failure that happened before ``run`` (daemon down, and so on)."""
        if self._log_written:
            return
        self._status = "stopped" if isinstance(exc, KeyboardInterrupt) else "error"
        self._error = "".join(traceback.format_exception(exc))
        self._write_log()

    def _print_startup(self) -> None:
        print("Ask Reachy")
        print(f"Condition: {self.condition}")
        print(f"motion_energy: {self.motion_energy:.2f}")
        print(f"Expected question: {EXPECTED_QUESTION}")
        print(f"Scripted answer: {SCRIPTED_ANSWER}")
        print(f"Run log: {self.log_path}")

    def _prepare_robot(self, reachy_mini: ReachyMini) -> None:
        # Torque on at the pose the robot already holds, then we move to neutral.
        reachy_mini.enable_motors()
        # Body yaw in the choreography is commanded, not copied from head yaw.
        reachy_mini.set_automatic_body_yaw(False)

    def _goto_neutral(
        self, reachy_mini: ReachyMini, stop_event: threading.Event | None = None
    ) -> None:
        if stop_event is not None and stop_event.is_set() and not self._cleaning_up:
            raise OperatorStop()
        print("Moving to neutral pose (head centered, antennas neutral, body yaw 0).")
        reachy_mini.goto_target(
            head=create_head_pose(degrees=True),
            antennas=list(NEUTRAL_ANTENNAS_RAD),
            body_yaw=NEUTRAL_BODY_YAW_RAD,
            duration=NEUTRAL_GOTO_DURATION_S,
            method="minjerk",
        )

    def _listen(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        print(f'Please ask out loud: "{EXPECTED_QUESTION}"')
        if self.simulate_question:
            print("Simulation listen: treating the question as heard.")
            self._question_heard = True
            return
        if not speech_backend_ready(reachy_mini):
            raise RuntimeError(
                "Reachy's microphone is not available. "
                "Start the daemon without --no-media, or pass --simulate-question "
                "when you only need to test motion."
            )
        heard = self._wait_for_utterance(reachy_mini, stop_event)
        if stop_event.is_set():
            raise OperatorStop()
        if not heard:
            raise RuntimeError(
                f"No speech detected within {self.listen_timeout_s:.0f} s."
            )
        self._question_heard = True
        print("Question heard. Speaking the scripted answer.")

    def _wait_for_utterance(
        self, reachy_mini: ReachyMini, stop_event: threading.Event
    ) -> bool:
        media = reachy_mini.media
        media.start_recording()
        heard = False
        speech_s = 0.0
        silence_s = 0.0
        deadline = time.monotonic() + self.listen_timeout_s
        try:
            print("Listening... (Ctrl+C returns Reachy to neutral and exits)")
            while time.monotonic() < deadline and not stop_event.is_set():
                sample = media.get_audio_sample()
                if sample is None:
                    time.sleep(0.02)
                    continue
                rms, chunk_s = _sample_rms(sample, media.get_input_audio_samplerate())
                if rms >= ONSET_RMS:
                    heard = True
                    speech_s += chunk_s
                    silence_s = 0.0
                elif heard:
                    silence_s += chunk_s
                    if speech_s >= MIN_SPEECH_S and silence_s >= END_SILENCE_S:
                        return True
            return False
        finally:
            try:
                media.stop_recording()
            except Exception as exc:
                print(f"Could not stop the microphone: {exc}", file=sys.stderr)

    def _speak_and_move(
        self, reachy_mini: ReachyMini, stop_event: threading.Event
    ) -> None:
        gestures = scaled_choreography(self.motion_energy)
        duration = answer_duration_s()
        can_speak = speech_backend_ready(reachy_mini)
        if not can_speak and not self.simulate_question:
            raise RuntimeError(
                "Reachy's speaker is not available, so this trial was not played. "
                "The answer file is "
                f"{ANSWER_WAV_PATH}."
            )
        if can_speak:
            print(f"Speaking ({duration:.2f} s) and playing choreography.")
            play_scripted_answer(reachy_mini)
            self._speech_played = True
        else:
            print(
                "Speaker is not available in this simulation. "
                "Playing the choreography on the scripted timeline."
            )
        speech_started = time.monotonic()
        for gesture in gestures:
            if stop_event.is_set():
                raise OperatorStop()
            print(
                f"  {gesture.name}: {gesture.duration_s:.2f} s, "
                f"pitch {gesture.pitch_deg:.1f} deg, "
                f"roll {gesture.roll_deg:.1f} deg, "
                f"yaw {gesture.yaw_deg:.1f} deg, "
                f"antennas ({gesture.right_antenna_rad:.3f}, {gesture.left_antenna_rad:.3f}) rad, "
                f"body_yaw {gesture.body_yaw_rad:.3f} rad"
            )
            reachy_mini.goto_target(
                head=create_head_pose(
                    z=gesture.z_m,
                    roll=gesture.roll_deg,
                    pitch=gesture.pitch_deg,
                    yaw=gesture.yaw_deg,
                    degrees=True,
                ),
                antennas=[gesture.right_antenna_rad, gesture.left_antenna_rad],
                body_yaw=gesture.body_yaw_rad,
                duration=gesture.duration_s,
                method="minjerk",
            )
        # If the recording is longer than the gestures, hold the last pose.
        # That wait is not an extra gesture.
        remaining = duration - (time.monotonic() - speech_started)
        if self._speech_played and remaining > 0:
            self._sleep(remaining, stop_event)

    def _sleep(self, seconds: float, stop_event: threading.Event) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if stop_event.is_set():
                raise OperatorStop()
            time.sleep(min(0.05, end - time.monotonic()))

    def _return_to_neutral(self, reachy_mini: ReachyMini) -> str:
        """Stop speech and the current gesture, then go back to the start pose."""
        print("Returning to the same neutral pose before exit.")
        try:
            reachy_mini.media.stop_playing()
        except Exception as exc:
            print(f"Could not stop audio: {exc}", file=sys.stderr)
        try:
            reachy_mini.client.send_command(StopMoveCmd())
        except Exception as exc:
            print(f"Could not stop the current move: {exc}", file=sys.stderr)
        time.sleep(0.15)
        try:
            self._goto_neutral(reachy_mini)
        except Exception:
            return traceback.format_exc()
        try:
            pose = np.asarray(reachy_mini.get_current_head_pose(), dtype=float)
            rotation = pose[:3, :3]
            cosine = float(np.clip((np.trace(rotation) - 1.0) / 2.0, -1.0, 1.0))
            angle_deg = float(np.degrees(np.arccos(cosine)))
            translation_m = float(np.linalg.norm(pose[:3, 3]))
            _, antennas = reachy_mini.get_current_joint_positions()
            antenna_err = float(np.linalg.norm(np.asarray(antennas, dtype=float)))
            self._neutral_error_deg = angle_deg
            print(
                f"Neutral check: head {angle_deg:.2f} deg from center, "
                f"translation {translation_m * 1000:.1f} mm, "
                f"antenna offset {antenna_err:.3f} rad."
            )
            if angle_deg > 5.0 or translation_m > 0.01 or antenna_err > 0.08:
                return (
                    "Robot did not finish at the neutral pose "
                    f"(head {angle_deg:.2f} deg, antennas {antenna_err:.3f} rad)."
                )
        except Exception:
            return traceback.format_exc()
        return ""

    def _write_log(self) -> None:
        if self._log_written:
            return
        gestures = []
        try:
            for gesture in scaled_choreography(self.motion_energy):
                gestures.append(
                    {
                        "name": gesture.name,
                        "duration_s": gesture.duration_s,
                        "roll_deg": gesture.roll_deg,
                        "pitch_deg": gesture.pitch_deg,
                        "yaw_deg": gesture.yaw_deg,
                        "z_m": gesture.z_m,
                        "right_antenna_rad": gesture.right_antenna_rad,
                        "left_antenna_rad": gesture.left_antenna_rad,
                        "body_yaw_rad": gesture.body_yaw_rad,
                    }
                )
        except Exception as exc:
            self._error = f"{self._error}\n{exc}".strip()
        record = {
            "condition": self.condition,
            "motion_energy": self.motion_energy,
            "start_timestamp": self.started_at,
            "end_timestamp": iso_now(),
            "completion_status": self._status,
            "error": self._error,
            "expected_question": EXPECTED_QUESTION,
            "scripted_answer": SCRIPTED_ANSWER,
            "question_heard": self._question_heard,
            "speech_played": self._speech_played,
            "simulate_question": self.simulate_question,
            "daemon_port": self.daemon_port,
            "neutral_head_error_deg": self._neutral_error_deg,
            "gestures": gestures,
        }
        path = write_run_record(record, self.log_path)
        self._log_written = True
        print(
            f"Logged {self._status}: condition {self.condition}, "
            f"motion_energy {self.motion_energy:.2f}, file {path}"
        )

    def _install_stop_handler(self, stop_event: threading.Event) -> None:
        def _handle(signum: int, frame: object) -> None:
            stop_event.set()
            print("\nCtrl+C received.")
            if self._cleaning_up:
                return
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, _handle)


def _sample_rms(sample: np.ndarray, sample_rate: int) -> tuple[float, float]:
    audio = np.asarray(sample, dtype=np.float32)
    if audio.size == 0:
        return 0.0, 0.02
    peak = float(np.max(np.abs(audio)))
    if peak > 1.5:
        audio = audio / 32768.0
    rms = float(np.sqrt(np.mean(np.square(audio))))
    rate = sample_rate if sample_rate and sample_rate > 0 else 16000
    return rms, audio.shape[0] / float(rate)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask Reachy: scripted spoken answer with a scaled gesture sequence."
    )
    parser.add_argument(
        "--motion-energy",
        type=float,
        default=None,
        help="Amplitude scale from 0.0 to 1.0. Study values: 0.25 (Reserved), 0.90 (Enthusiastic).",
    )
    parser.add_argument(
        "--simulate-question",
        action="store_true",
        help="Skip the microphone and treat the question as heard. Use this in simulation.",
    )
    parser.add_argument(
        "--listen-timeout",
        type=float,
        default=45.0,
        help="Seconds to wait for the spoken question (default: 45).",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help=f"JSONL run log. Default: {DEFAULT_LOG_PATH}",
    )
    parser.add_argument(
        "--daemon-port",
        type=int,
        default=8000,
        help="Daemon HTTP port. Default 8000. Use another port only when a simulation daemon is not the one on 8000.",
    )
    args = parser.parse_args(argv)
    if args.motion_energy is None and os.environ.get("ASK_REACHY_MOTION_ENERGY"):
        args.motion_energy = float(os.environ["ASK_REACHY_MOTION_ENERGY"])
    if os.environ.get("ASK_REACHY_SIMULATE_QUESTION") == "1":
        args.simulate_question = True
    if args.motion_energy is None:
        parser.error(
            "Pass --motion-energy. Reserved is 0.25. Enthusiastic is 0.90."
        )
    args.motion_energy = validate_energy(args.motion_energy)
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    app = AskReachy(
        motion_energy=args.motion_energy,
        simulate_question=args.simulate_question,
        listen_timeout_s=args.listen_timeout,
        log_path=args.log_file,
        started_at=iso_now(),
        daemon_port=args.daemon_port,
    )
    print("Ask Reachy")
    print(f"Condition: {app.condition}")
    print(f"motion_energy: {app.motion_energy:.2f}")
    try:
        app.wrapped_run(port=args.daemon_port)
    except BaseException as exc:
        app.record_connection_failure(exc)
        if isinstance(exc, KeyboardInterrupt):
            raise SystemExit(130) from exc
        raise


if __name__ == "__main__":
    main()
