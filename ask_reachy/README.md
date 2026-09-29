---
title: Ask Reachy
emoji: 🎙️
colorFrom: red
colorTo: blue
sdk: static
pinned: false
short_description: Scripted spoken answer with two movement energies.
tags:
 - reachy_mini
 - reachy_mini_python_app
---

# Ask Reachy

Ask Reachy is a spoken question-and-answer trial for Reachy Mini. The participant asks one fixed question. Reachy always speaks the same recording, and while it speaks it plays one gesture sequence. A single number, `motion_energy`, scales how large those gestures are. The sequence, the number of gestures, their order, and their durations stay the same.

This is a Python app. It uses the Reachy Mini microphone and speaker the way the conversation app does, and it moves with `goto_target` the way Coding Lab does. The answer is not written by a language model.

## The two conditions

| Condition | Label | `motion_energy` |
| --- | --- | --- |
| A | Reserved (shy) | `0.25` |
| B | Enthusiastic | `0.90` |

The value is printed at startup and written to the run log. `0.25` and `0.90` are the study values. The program also accepts any number from `0.0` to `1.0` and labels anything else `Custom`.

Reserved is a shy posture: antennas folded down, head lowered and pitched down. Enthusiastic bobs the head between 24° up and 24° down and reverses the antennas every 0.50 s, the shortest smooth move. Both stay inside the hardware limits (head pitch and roll ±40 degrees). The run still starts and ends at the neutral pose.

## What Reachy says

Ask this, out loud, every trial:

> Reachy, what do you like to do?

Reachy always answers with this recording (`ask_reachy/assets/answer.wav`, about 6.5 seconds):

> I like meeting people and answering questions. I listen first, then I speak while my head and antennas move with me.

The text lives in `ask_reachy/speech.py` as `SCRIPTED_ANSWER`. The program refuses to play the WAV if `ask_reachy/assets/answer.txt` does not match that string.

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

`pip install -e .` registers the app (`ask_reachy`) so the daemon dashboard can see it. For a study trial, start it from the terminal with the flag below so the condition is explicit. The dashboard launches the module without arguments. You can pin a condition for that launch by setting `ASK_REACHY_MOTION_ENERGY` first (`0.25` or `0.90`).

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

Condition A, Reserved:

```bash
python -m ask_reachy.main --motion-energy 0.25 --simulate-question
```

Condition B, Enthusiastic:

```bash
python -m ask_reachy.main --motion-energy 0.90 --simulate-question
```

`--simulate-question` skips the microphone and treats the question as heard, so you can check the motion without a robot mic. The startup lines must show `motion_energy: 0.25` or `motion_energy: 0.90`.

Simulation does not exercise the real microphone, the robot speaker, or the real motors. If the speaker backend is missing, the app still plays the gesture sequence and records `speech_played: false`. On a physical robot, a missing speaker aborts the trial and still returns to neutral.

## Physical robot

Do this only after a simulation run has finished and returned to neutral.

1. Stop the simulation daemon (Ctrl+C in that terminal). Only one daemon should be running.
2. Lite (USB): start `reachy-mini-daemon` with no `--sim` flag. Wireless: power the robot on and wait until it is on the network. The daemon on a Wireless robot starts by itself.
3. Give the head and antennas a clear space. The first physical motions should be the two commands below, not a higher energy.
4. Do **not** pass `--simulate-question`. Reachy should hear the question on its microphone and play `answer.wav` on its speaker.

Condition A, Reserved:

```bash
python -m ask_reachy.main --motion-energy 0.25
```

Condition B, Enthusiastic:

```bash
python -m ask_reachy.main --motion-energy 0.90
```

When the program prints the question, ask: "Reachy, what do you like to do?" It waits up to 45 seconds, then speaks. Speech has to rise above a modest loudness and then go quiet for about 0.8 seconds before the answer starts.

Nothing else changes between simulation and the robot: same app, same energies, same recording, same gesture list. The daemon command and the microphone are the difference. Wireless robots are reached over the network; Lite robots use a daemon on the laptop. If you are on the same machine as the daemon, the app connects to localhost.

## Stop procedure

1. Press Ctrl+C once in the terminal that is running Ask Reachy.
2. Leave the process alone. It stops the current gesture and the audio, moves back to the neutral pose (about 1.2 seconds), writes the log with `completion_status` `stopped`, and exits.
3. A second Ctrl+C during that return is ignored so the robot can finish the neutral move.
4. If a crash leaves Reachy away from neutral, start the app again. The first motion is the move to neutral. You can press Ctrl+C at the "Please ask out loud" line if you do not want a full trial.

## Logs

Each run appends one JSON line to `logs/ask_reachy_runs.jsonl` (or to `--log-file`). The file is created on the first run. The record includes:

- `condition` (`Reserved`, `Enthusiastic`, or `Custom`)
- `motion_energy`
- `start_timestamp` and `end_timestamp` (local time, with the offset)
- `completion_status`: `completed`, `stopped`, or `error`
- `error` (empty when the run completed)
- whether the question was heard and whether the WAV was played
- the scaled gesture list that was commanded
- how far the head was from center after the final neutral move

A connection failure before the trial starts is logged too, with status `error`.

## The gesture sequence

Reserved uses eight slow poses. Both antennas stay folded down (`-3.05` and `+3.05` rad, the same pose as sleep), and the head stays lowered and pitched down (about 32° to 36°) so the face is nearly hidden.

Enthusiastic uses thirteen half-second beats, starting with the head tipped up, then down, and alternating from there. The antennas swap direction on every beat (`+1.20` / `-1.20` rad, then the reverse), so they move about twice a second through the answer.

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
