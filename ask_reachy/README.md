---
title: Ask Reachy
emoji: 🎙️
colorFrom: red
colorTo: blue
sdk: static
pinned: false
short_description: Two-story session with shy or curious movement.
tags:
 - reachy_mini
 - reachy_mini_python_app
---

# Ask Reachy

Ask Reachy is one two-story session for Reachy Mini. Reachy speaks a fixed script. Each session shuffles which prompt comes first and which movement style is paired with it. Shy and curious are each used once. The words, the voice, and the 5 second pause that ends a turn stay the same.

The terminal prints the assignment, the seed, each response length, the transcript, and Yes or No for the continue question. Write the participant ID on the session sheet. The questionnaire, and whether a condition was interrupted, failed, or repeated, stay on that sheet too.

This is a Python app. It uses the Reachy Mini microphone and speaker, and it moves with `goto_target`. Transcripts are made on this computer. The story is not sent to a chat model.

## The two conditions

| Characteristic | `motion_energy` | Movement |
| --- | --- | --- |
| Shy | `0.25` | Antennas folded down, head lowered |
| Curious | `0.90` | Head bobs between 24° up and 24° down, antennas reverse every 0.50 s |

Both stay inside the hardware limits (head pitch and roll ±40 degrees). The introduction, the pause between stories, and the final line are in the neutral pose. Each story starts from neutral, then uses that story's characteristic while Reachy is speaking.

## What Reachy says

The introduction is in the neutral pose:

> Hi there, I'm Reachy Mini, your storytelling companion. In this task, we will work together to write a story.

Prompt A:

> It's fall in New York. You find a handwritten note tucked beneath a pile of fallen leaves. What happens next?

Prompt B:

> It's fall in New York. While walking down a familiar street, you notice something that wasn't there yesterday. What happens next?

After the prompt, Reachy listens. A turn ends when speech has lasted at least 0.35 seconds and then stays quiet for 5 seconds. The terminal prints the participant's speaking time immediately, in seconds. Short pauses inside the reply count. The 5 second ending pause does not. The transcript prints when it is ready, with that same time beside it.

Reachy listens after the prompt, then says these three lines in order, listening after each of the first two:

1. That's interesting. What's next?
2. That's interesting. What's next?
3. Interesting story. Would you like to continue expanding it?

The third line is followed by one more listen. The terminal records that answer as Yes, No, or Unclear. Either answer gets the same goodbye:

> Thank you for your participation. That's the end of Story 1.

Story 2 uses the same lines and says "Story 2". After both stories, still in the neutral pose:

> That conclude our study. Thank you so much for your participation.

Each line is a checked-in WAV (macOS Samantha, 160 words per minute) next to a text file in `ask_reachy/assets/`. The program refuses to play a WAV if its text file does not match `ask_reachy/speech.py`. Do not regenerate the WAVs mid-study.

Spoken lines are often shorter than the gesture sequence (about 6.4 seconds). Reachy finishes the movement, then listens again. Both characteristics use that same gap.

## Neutral pose

Every run starts by moving here, and every run ends by moving back here, including after Ctrl+C or an error:

- Head centered (no roll, pitch, or yaw, and no position offset)
- Antennas at `0` radians
- Body yaw at `0` radians

The move into and out of that pose takes 1.2 seconds and uses minimum-jerk interpolation. The SDK's wake-up pose uses a small antenna offset (about ±10 degrees) to reduce buzzing. This app uses exact zeros so the start pose and the end pose are the same measured pose. If the physical antennas buzz at zero, change `NEUTRAL_ANTENNAS_RAD` in `ask_reachy/choreography.py` and use that same value for both the start and the end. Do not change only one of them.

## Setup

Follow the [Reachy Mini installation guide](https://huggingface.co/docs/reachy_mini/SDK/installation). Simulation needs the MuJoCo extra.

```bash
uv venv reachy_mini_env --python 3.12
source reachy_mini_env/bin/activate
uv pip install "reachy-mini[mujoco]"
```

Then install this app from the `ask_reachy` directory:

```bash
uv pip install -e .
```

`pip install -e .` registers the app (`ask_reachy`) so the daemon dashboard can see it. A study trial is one launch. The program shuffles prompt order and shy/curious by itself and prints the assignment. Transcripts need `faster-whisper` (`pip install faster-whisper`). Without it, lengths are still recorded and transcripts stay empty.

## Simulation first

In one terminal, start a simulated robot. Headless MuJoCo:

```bash
reachy-mini-daemon --sim --headless
```

If MuJoCo is not installed, use the lightweight simulator instead:

```bash
reachy-mini-daemon --mockup-sim
```

Leave that process running. Confirm it is the simulator before you launch a trial:

```bash
curl -s http://127.0.0.1:8000/api/daemon/status
```

`simulation_enabled` must be `true`. If it is `false`, port 8000 is a physical robot. Stop that daemon or start the simulator on another port (`reachy-mini-daemon --sim --headless --fastapi-port 8001`) and add `--daemon-port 8001` to the commands below.

In a second terminal, from this directory, with the environment activated:

```bash
python -m ask_reachy.main --simulate-question
```

`--simulate-question` skips the microphone and plays the full two-story script, including both movement styles. The startup lines print the seed and which prompt is shy or curious. Pass `--seed 7` to repeat an assignment.

Simulation does not exercise the real microphone, the robot speaker, or the real motors. If the speaker backend is missing, the app still plays the gesture sequence and records `speech_played: false`. On a physical robot, a missing speaker aborts the trial and still returns to neutral.

## Physical robot

Do this only after a simulation run has finished and returned to neutral.

1. Stop the simulation daemon (Ctrl+C in that terminal). Only one daemon should be running.
2. Lite (USB): start `reachy-mini-daemon` with no `--sim` flag. Wireless: power the robot on and wait until it is on the network. The daemon on a Wireless robot starts by itself.
3. Give the head and antennas a clear space.
4. Do **not** pass `--simulate-question`.

```bash
python -m ask_reachy.main
```

Read the assignment in the terminal before the participant begins. Reachy speaks the introduction, then the first prompt. A 5 second pause ends each turn. If nobody speaks for 90 seconds, that turn is recorded as empty and the script continues.

Nothing else changes between simulation and the robot: same app, same energies, same recording, same gesture list. The daemon command and the microphone are the difference. Wireless robots are reached over the network; Lite robots use a daemon on the laptop. If you are on the same machine as the daemon, the app connects to localhost.

## Stop procedure

1. Press Ctrl+C once in the terminal that is running Ask Reachy.
2. Leave the process alone. It stops the current gesture and the audio, moves back to the neutral pose (about 1.2 seconds), writes the log with `completion_status` `stopped`, and exits.
3. A second Ctrl+C during that return is ignored so the robot can finish the neutral move.
4. If a crash leaves Reachy away from neutral, start the app again. The first motion is the move to neutral. You can press Ctrl+C at the "Listening..." line if you do not want a full trial. Ctrl+C does not play the closing line.

## Logs

Each run appends one JSON line to `logs/ask_reachy_runs.jsonl` (or to `--log-file`). The file is created on the first run. The record includes:

- `seed` and `assignment` (story number, prompt A or B, Shy or Curious, `motion_energy`)
- `start_timestamp` and `end_timestamp` (local time, with the offset)
- `interaction_start_timestamp` and `interaction_end_timestamp`
- `completion_status`: `completed`, `stopped`, or `error`
- `error` (empty when the run completed)
- per story: response lengths, transcripts, the continue answer (Yes, No, or Unclear), and the gesture list
- whether a WAV was played
- how far the head was from center after the final neutral move

Participant ID is not in this file. Record it on the session sheet. The assignment in this file is the one the robot used.

A connection failure before the trial starts is logged too, with status `error`.

## The gesture sequence

Shy uses eight slow poses. Both antennas stay folded down (`-3.05` and `+3.05` rad, the same pose as sleep), and the head stays lowered and pitched down (about 32° to 36°) so the face is nearly hidden.

Curious uses thirteen half-second beats, starting with the head tipped up, then down, and alternating from there. The antennas swap direction on every beat (`+1.20` / `-1.20` rad, then the reverse), so they move about twice a second through each response.

Any other `motion_energy` scales the open sequence below. The run still starts and ends at the neutral pose.

| Gesture | Duration | What moves at full scale |
| --- | --- | --- |
| nod | 0.70 s | pitch −12° |
| antennas_lift | 0.65 s | antennas +0.40 / −0.40 rad |
| tilt_right | 0.90 s | roll +14°, yaw +8° |
| sway_left | 0.90 s | roll −14°, antennas −0.35 / +0.35 rad |
| emphasis_nod | 0.70 s | pitch −14°, antennas +0.25 / −0.25 rad |
| body_glance | 0.95 s | yaw +8°, body yaw +0.15 rad |
| antenna_wave | 0.80 s | roll +6°, antennas −0.40 / +0.40 rad |
| open_settle | 0.80 s | pitch +8°, antennas +0.20 / −0.20 rad |

Antenna order is right, then left, in radians, matching the SDK. Head translation stays at zero. Speech-reactive head wobble is off, so the recording does not add extra motion on top of this list.

Check the scaling without a robot:

```bash
python -m unittest tests/test_choreography.py
```
