"""Two-story session with Reachy: same words, shuffled prompt and style.

Reachy introduces the task in the neutral pose, then runs two stories.
Each story is one prompt, then three participant turns. After the first
two turns Reachy says "That's interesting. What's next?" After the third
it asks whether to continue, records Yes or No, and closes that story.
Both stories use the same lines. Only the movement style changes.

The terminal prints the shuffled assignment before anything moves, then
each response length as soon as the participant pauses. The transcript
is filled in afterward so Reachy's next line is not waiting on it.
"""

from __future__ import annotations

import argparse
import os
import random
import signal
import sys
import tempfile
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.io.protocol import StopMoveCmd
from reachy_mini.utils import create_head_pose

from ask_reachy.choreography import (
    NEUTRAL_ANTENNAS_RAD,
    NEUTRAL_BODY_YAW_RAD,
    NEUTRAL_GOTO_DURATION_S,
    scaled_choreography,
)
from ask_reachy.run_log import DEFAULT_LOG_PATH, iso_now, write_run_record
from ask_reachy.speech import (
    END_STORY,
    INTRO,
    STORY_FOLLOWUPS,
    STUDY_CLOSING,
    StorySlot,
    line_duration_s,
    load_all_lines,
    plan_session,
    play_line,
    speech_backend_ready,
)
from ask_reachy.transcribe import (
    classify_yes_no,
    load_recognizer,
    transcribe_wav,
    write_turn_wav,
)

# A turn ends after this much quiet. Five seconds is the study rule.
ONSET_RMS = 0.02
END_SILENCE_S = 5.0
MIN_SPEECH_S = 0.35
# If nobody starts talking, do not leave Reachy waiting forever.
SPEECH_START_TIMEOUT_S = 90.0


class OperatorStop(Exception):
    """The operator asked the trial to stop. Reachy still returns to neutral."""


@dataclass
class TurnRecord:
    """One participant turn. The transcript arrives after Reachy has moved on."""

    kind: str
    duration_s: float
    transcript: str = ""
    yes_no: str = ""
    error: str = ""
    done: threading.Event = field(default_factory=threading.Event)


class AskReachy(ReachyMiniApp):
    """One participant, two stories, shy and curious each used once."""

    # Terminal study app. A settings page could change a trial, so it stays off.
    custom_app_url: str | None = None
    dont_start_webserver: bool = True

    def __init__(
        self,
        plan: tuple[StorySlot, StorySlot],
        seed: int,
        simulate_question: bool = False,
        log_path: Path | None = None,
        started_at: str | None = None,
        daemon_port: int = 8000,
    ) -> None:
        super().__init__()
        self.plan = plan
        self.seed = seed
        self.simulate_question = simulate_question
        self.log_path = log_path or DEFAULT_LOG_PATH
        self.started_at = started_at or iso_now()
        self.daemon_port = daemon_port
        self._log_written = False
        self._cleaning_up = False
        self._status = "error"
        self._error = ""
        self._speech_played = False
        self._lines_played: list[str] = []
        self._story_records: list[dict] = []
        self._pending: list[TurnRecord] = []
        self._interaction_started_at = ""
        self._interaction_ended_at = ""
        self._neutral_error_deg: float | None = None
        self._print_lock = threading.Lock()

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        """Run both stories, then return to the same neutral pose."""
        self._install_stop_handler(stop_event)
        try:
            load_all_lines()
            self._print_assignment()
            if not self.simulate_question:
                print("Loading speech recognition. The first run may download a model.")
                recognizer_error = load_recognizer()
                if recognizer_error:
                    print(recognizer_error, file=sys.stderr)
            self._prepare_robot(reachy_mini)
            self._goto_neutral(reachy_mini, stop_event)
            self._interaction_started_at = iso_now()
            self._speak(reachy_mini, stop_event, INTRO, motion_energy=None)
            for number, slot in enumerate(self.plan, start=1):
                self._run_story(reachy_mini, stop_event, number, slot)
            self._goto_neutral(reachy_mini, stop_event)
            self._speak(reachy_mini, stop_event, STUDY_CLOSING, motion_energy=None)
            self._interaction_ended_at = iso_now()
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
            if not self._interaction_ended_at:
                self._interaction_ended_at = iso_now()
            cleanup_error = self._return_to_neutral(reachy_mini)
            if cleanup_error and self._status == "completed":
                self._status = "error"
            if cleanup_error:
                self._error = (
                    f"{self._error}\n{cleanup_error}".strip()
                    if self._error
                    else cleanup_error
                )
            self._finish_transcripts()
            self._write_log()

    def record_connection_failure(self, exc: BaseException) -> None:
        """Log a failure that happened before ``run`` (daemon down, and so on)."""
        if self._log_written:
            return
        self._status = "stopped" if isinstance(exc, KeyboardInterrupt) else "error"
        self._error = "".join(traceback.format_exception(exc))
        self._write_log()

    def _print_assignment(self) -> None:
        print("Ask Reachy — two-story session")
        print(f"Seed: {self.seed}")
        print("Assignment (record this before the participant starts):")
        for number, slot in enumerate(self.plan, start=1):
            style = slot.characteristic
            print(
                f"  Story {number}: Prompt {slot.prompt.key} — {style.name} "
                f"(motion_energy {style.motion_energy:.2f})"
            )
            print(f"    {slot.prompt.line.text}")
        print(f"Introduction, neutral pose: {INTRO.text}")
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

    def _run_story(
        self,
        reachy_mini: ReachyMini,
        stop_event: threading.Event,
        number: int,
        slot: StorySlot,
    ) -> None:
        style = slot.characteristic
        print(
            f"--- Story {number}: Prompt {slot.prompt.key} — {style.name} "
            f"(motion_energy {style.motion_energy:.2f}) ---"
        )
        self._goto_neutral(reachy_mini, stop_event)
        self._speak(
            reachy_mini,
            stop_event,
            slot.prompt.line,
            motion_energy=style.motion_energy,
        )
        responses: list[TurnRecord] = []
        story_record: dict = {
            "story": number,
            "prompt": slot.prompt.key,
            "prompt_text": slot.prompt.line.text,
            "characteristic": style.name,
            "motion_energy": style.motion_energy,
            "responses": responses,
            "continue_answer": None,
        }
        # Kept even if the story is stopped midway, so those turns stay in the log.
        self._story_records.append(story_record)
        for index, followup in enumerate(STORY_FOLLOWUPS, start=1):
            label = f"Story {number} response {index}"
            turn = self._listen(reachy_mini, stop_event, label, kind="story")
            responses.append(turn)
            self._speak(
                reachy_mini,
                stop_event,
                followup,
                motion_energy=style.motion_energy,
            )
            if followup is STORY_FOLLOWUPS[-1]:
                story_record["continue_answer"] = self._listen(
                    reachy_mini,
                    stop_event,
                    f"Story {number} continue answer",
                    kind="yes_no",
                )
        self._speak(
            reachy_mini,
            stop_event,
            END_STORY[number],
            motion_energy=style.motion_energy,
        )

    def _listen(
        self,
        reachy_mini: ReachyMini,
        stop_event: threading.Event,
        label: str,
        kind: str,
    ) -> TurnRecord:
        if self.simulate_question:
            print(f"{label}: simulation, microphone skipped.")
            record = TurnRecord(kind=kind, duration_s=0.0)
            if kind == "yes_no":
                record.yes_no = "Unclear"
            record.done.set()
            return record
        if not speech_backend_ready(reachy_mini):
            raise RuntimeError(
                "Reachy's microphone and speaker are not available. "
                "Start the daemon without --no-media, or pass --simulate-question "
                "when you only need to test motion."
            )
        audio, duration_s, sample_rate = self._record_turn(reachy_mini, stop_event)
        record = TurnRecord(kind=kind, duration_s=duration_s)
        self._pending.append(record)
        print(f"{label} — participant speaking time: {duration_s:.1f} s", flush=True)
        if audio:
            worker = threading.Thread(
                target=self._transcribe_later,
                args=(record, audio, sample_rate, label),
                daemon=True,
            )
            worker.start()
        else:
            if kind == "yes_no":
                record.yes_no = "Unclear"
            record.transcript = ""
            self._emit(f"{label} transcript: (no speech)")
            if kind == "yes_no":
                self._emit(f"{label} Yes/No: Unclear")
            record.done.set()
        return record

    def _record_turn(
        self, reachy_mini: ReachyMini, stop_event: threading.Event
    ) -> tuple[list[np.ndarray], float, int]:
        """Record until 5 s of quiet. Return samples, speaking length, rate."""
        media = reachy_mini.media
        try:
            media.stop_playing()
        except Exception:
            pass
        media.start_recording()
        heard = False
        speech_s = 0.0
        silence_s = 0.0
        # Pauses shorter than 5 s stay inside the response. The ending pause does not.
        inside_pause_s = 0.0
        chunks: list[np.ndarray] = []
        sample_rate = 16000
        wait_started = time.monotonic()
        try:
            print("Listening... (a 5 s pause ends the turn; Ctrl+C returns to neutral)")
            while not stop_event.is_set():
                if not heard and time.monotonic() - wait_started >= SPEECH_START_TIMEOUT_S:
                    print(f"No speech detected within {SPEECH_START_TIMEOUT_S:.0f} s.")
                    return [], 0.0, sample_rate
                sample = media.get_audio_sample()
                if sample is None:
                    time.sleep(0.02)
                    if heard:
                        silence_s += 0.02
                        if speech_s >= MIN_SPEECH_S and silence_s >= END_SILENCE_S:
                            return chunks, speech_s + inside_pause_s, sample_rate
                    continue
                try:
                    sample_rate = int(media.get_input_audio_samplerate() or sample_rate)
                except Exception:
                    pass
                rms, chunk_s = _sample_rms(sample, sample_rate)
                if rms >= ONSET_RMS:
                    if heard and silence_s > 0.0:
                        inside_pause_s += silence_s
                    heard = True
                    speech_s += chunk_s
                    silence_s = 0.0
                    chunks.append(np.array(sample, copy=True))
                elif heard:
                    silence_s += chunk_s
                    chunks.append(np.array(sample, copy=True))
                    if speech_s >= MIN_SPEECH_S and silence_s >= END_SILENCE_S:
                        return chunks, speech_s + inside_pause_s, sample_rate
            raise OperatorStop()
        finally:
            try:
                media.stop_recording()
            except Exception as exc:
                print(f"Could not stop the microphone: {exc}", file=sys.stderr)

    def _transcribe_later(
        self,
        record: TurnRecord,
        chunks: list[np.ndarray],
        sample_rate: int,
        label: str,
    ) -> None:
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "turn.wav"
                write_turn_wav(chunks, sample_rate, path)
                text, error = transcribe_wav(path)
            record.transcript = text
            record.error = error
            if record.kind == "yes_no":
                record.yes_no = classify_yes_no(text) if text else "Unclear"
            shown = text if text else "(empty)"
            timed = f"{label} ({record.duration_s:.1f} s)"
            if error:
                self._emit(f"{timed} transcript unavailable: {error}")
            else:
                self._emit(f"{timed} transcript: {shown}")
            if record.kind == "yes_no":
                self._emit(f"{label} Yes/No: {record.yes_no}")
        except Exception as exc:
            record.error = str(exc)
            if record.kind == "yes_no" and not record.yes_no:
                record.yes_no = "Unclear"
            self._emit(f"{label} transcript unavailable: {exc}")
        finally:
            record.done.set()

    def _finish_transcripts(self) -> None:
        for record in self._pending:
            record.done.wait(timeout=180.0)

    def _speak(
        self,
        reachy_mini: ReachyMini,
        stop_event: threading.Event,
        line,
        motion_energy: float | None,
    ) -> None:
        """Play one fixed line. Movement runs only when a characteristic is set."""
        if stop_event.is_set():
            raise OperatorStop()
        duration = line_duration_s(line)
        can_speak = speech_backend_ready(reachy_mini)
        if not can_speak and not self.simulate_question:
            raise RuntimeError(
                "Reachy's speaker is not available, so this trial was not played. "
                f"The line was {line.text!r}."
            )
        self._lines_played.append(line.text)
        if motion_energy is None:
            where = "neutral pose"
        else:
            where = f"motion_energy {motion_energy:.2f}"
        if can_speak:
            print(f'Reachy ({where}): "{line.text}" ({duration:.2f} s)')
            play_line(reachy_mini, line)
            self._speech_played = True
        else:
            print(
                f'Reachy would say ({where}): "{line.text}". '
                "Speaker is not available in this simulation."
            )
        speech_started = time.monotonic()
        if motion_energy is not None:
            for gesture in scaled_choreography(motion_energy):
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
        remaining = duration - (time.monotonic() - speech_started)
        if can_speak and remaining > 0:
            self._sleep(remaining, stop_event)
        elif motion_energy is None and not can_speak:
            self._sleep(duration, stop_event)

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
        stories = []
        for story in self._story_records:
            gestures = []
            try:
                for gesture in scaled_choreography(story["motion_energy"]):
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
            continue_turn: TurnRecord | None = story["continue_answer"]
            stories.append(
                {
                    "story": story["story"],
                    "prompt": story["prompt"],
                    "prompt_text": story["prompt_text"],
                    "characteristic": story["characteristic"],
                    "motion_energy": story["motion_energy"],
                    "responses": [_turn_dict(turn) for turn in story["responses"]],
                    "continue_answer": "" if continue_turn is None else continue_turn.yes_no,
                    "continue_transcript": ""
                    if continue_turn is None
                    else continue_turn.transcript,
                    "continue_duration_s": 0.0
                    if continue_turn is None
                    else round(continue_turn.duration_s, 3),
                    "gestures": gestures,
                }
            )
        record = {
            "seed": self.seed,
            "assignment": [
                {
                    "story": number,
                    "prompt": slot.prompt.key,
                    "prompt_text": slot.prompt.line.text,
                    "characteristic": slot.characteristic.name,
                    "motion_energy": slot.characteristic.motion_energy,
                }
                for number, slot in enumerate(self.plan, start=1)
            ],
            "start_timestamp": self.started_at,
            "interaction_start_timestamp": self._interaction_started_at,
            "interaction_end_timestamp": self._interaction_ended_at,
            "end_timestamp": iso_now(),
            "completion_status": self._status,
            "error": self._error,
            "lines_played": self._lines_played,
            "speech_played": self._speech_played,
            "simulate_question": self.simulate_question,
            "daemon_port": self.daemon_port,
            "neutral_head_error_deg": self._neutral_error_deg,
            "stories": stories,
        }
        path = write_run_record(record, self.log_path)
        self._log_written = True
        print(f"Logged {self._status}: seed {self.seed}, file {path}")

    def _emit(self, text: str) -> None:
        with self._print_lock:
            print(text, flush=True)

    def _install_stop_handler(self, stop_event: threading.Event) -> None:
        def _handle(signum: int, frame: object) -> None:
            stop_event.set()
            print("\nCtrl+C received.")
            if self._cleaning_up:
                return
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, _handle)


def _turn_dict(turn: TurnRecord) -> dict:
    return {
        "kind": turn.kind,
        "duration_s": round(turn.duration_s, 3),
        "transcript": turn.transcript,
        "error": turn.error,
    }


def _sample_rms(sample: np.ndarray, sample_rate: int) -> tuple[float, float]:
    audio = np.asarray(sample, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.reshape(-1, audio.shape[-1])
        audio = audio.mean(axis=1)
    audio = audio.reshape(-1)
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
        description=(
            "Ask Reachy: two stories, same lines, shuffled prompt and shy/curious movement."
        )
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Shuffle seed. Printed either way so the assignment can be repeated.",
    )
    parser.add_argument(
        "--simulate-question",
        action="store_true",
        help="Skip the microphone and play both stories without transcripts.",
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
        help="Daemon HTTP port. Default 8000.",
    )
    args = parser.parse_args(argv)
    if os.environ.get("ASK_REACHY_SIMULATE_QUESTION") == "1":
        args.simulate_question = True
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 2**31)
    plan = plan_session(random.Random(seed))
    app = AskReachy(
        plan=plan,
        seed=seed,
        simulate_question=args.simulate_question,
        log_path=args.log_file,
        started_at=iso_now(),
        daemon_port=args.daemon_port,
    )
    app._print_assignment()
    try:
        app.wrapped_run(port=args.daemon_port)
    except BaseException as exc:
        app.record_connection_failure(exc)
        if isinstance(exc, KeyboardInterrupt):
            raise SystemExit(130) from exc
        raise


if __name__ == "__main__":
    main()
