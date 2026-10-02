# Lab 2: Ask Reachy

This project uses Reachy Mini as a storytelling partner. The idea is to compare how people respond to two movement styles: **Shy** and **Curious**. Each session includes two stories, with one style used for each story. The app shuffles the prompt order and which style goes with each prompt.

The words and recorded voice stay the same across the two conditions. Shy uses a motion energy of `0.25`, and Curious uses `0.90`. The app records how long participants speak, their transcripts, and whether they want to keep going.

## Setup

You need Git and Python 3.10 or newer. The project was developed on macOS with Python 3.11.9. For the robot setup, see the [Reachy Mini installation guide](https://huggingface.co/docs/reachy_mini/SDK/installation).

```bash
git clone https://github.com/fanning13/ReachyminiLab2.git
cd ReachyminiLab2
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ./ask_reachy
```

On Windows PowerShell, replace the activation line with:

```powershell
.\.venv\Scripts\Activate.ps1
```

The install includes the Reachy Mini SDK and `faster-whisper`. Transcription runs locally using the English `base.en` model, which may need to download on the first run. No API key is needed.

Run the commands below from the repository root with the environment activated. This is a terminal app; you do not need to open the HTML files.

## Connecting to the course robot

These steps are a short version of the course's *Reachy Mini Access and Basic Testing Guide*. Use your assigned robot and the login details provided in class.

### Option 1: Course VM

1. Set up Cornell two-factor authentication and connect to RedRover. For off-campus access, follow the course's Cornell VPN instructions.
2. Open Remote Desktop and connect to your assigned VM using the hostname in the course guide. Use your Cornell email for the initial sign-in if prompted, then your NetID at the VM login screen.
3. Power on your assigned robot. In the VM terminal, SSH into it using the robot hostname from the guide:

   ```bash
   ssh -l pollen <your-robot-hostname>
   ```

   Replace `<your-robot-hostname>` with the assigned hostname and enter the robot password supplied in class.

4. In the robot's SSH terminal, check the existing daemon and activate the installed Python environment:

   ```bash
   systemctl is-active reachy-mini-daemon
   source /venvs/mini_daemon/bin/activate
   python -c "import reachy_mini; print(reachy_mini.__file__)"
   ```

   The first command should print `active`, and the last should print the SDK's file path. If the daemon is inactive, contact the instructor. Do not start a second daemon on the course robot.

### Option 2: Classroom network

In Tata 429, connect to the class WiFi network using the details provided in class and turn on your robot. Open **Reachy Mini Control**, select your assigned robot's detected IP address (or use its address from the course guide), and click **Connect**. This connects the control app; it does not install Ask Reachy.

To use the same robot-terminal workflow as above, open a terminal on your computer and run `ssh -l pollen <your-robot-ip>`, replacing the placeholder with your assigned robot's address. Then check the daemon and activate the environment using the commands above.

### Quick motion check

With space around the antennas, run this in the robot's SSH terminal after activating the environment:

```bash
python - <<'PY'
from reachy_mini import ReachyMini

with ReachyMini() as mini:
    mini.enable_motors()
    print("Connected, moving antennas...")
    for pose in ([0.3, -0.3], [-0.3, 0.3], [0.0, 0.0]):
        mini.goto_target(antennas=pose, duration=1.0)
    print("Done")
PY
```

The antennas should move in opposite directions, reverse, and return to neutral. This checks motion only; check the microphone and speaker before running a participant session.

For Ask Reachy, clone this repository in the robot's SSH terminal, enter the repository folder, and run `python -m pip install -e ./ask_reachy` in the activated environment. Use the existing `/venvs/mini_daemon` environment for this course workflow instead of creating the laptop `.venv` above. Then use the participant-session command below, without starting another daemon. Keep simulation runs on your own computer. When finished, stop the app, let it return to neutral, and type `exit` to leave SSH.

## Running the app

### Try it in simulation

Open two terminals. In the first one, start the mock simulator:

```bash
reachy-mini-daemon --mockup-sim
```

In the second one, run:

```bash
python -m ask_reachy.main --simulate-question --seed 7 --log-file ask_reachy/logs/simulation.jsonl
```

Before running, open `http://127.0.0.1:8000/api/daemon/status` and check that `simulation_enabled` is `true`. The `--simulate-question` flag only skips the microphone, so it is still important to connect to a simulated robot.

The terminal shows the prompt order, movement styles, seed, and log location. Using the same seed repeats the assignment. Simulation skips participant responses, so its durations are zero and its transcripts are empty. Do not use these records as study data.

For MuJoCo simulation instead, install the extra and use this daemon command:

```bash
python -m pip install "reachy-mini[mujoco]"
reachy-mini-daemon --sim --headless
```

### Run with Reachy Mini

If using the course robot, keep its existing daemon running and use the SSH setup above. For your own robot, stop the simulation daemon first. For Reachy Mini Lite, connect the robot and start `reachy-mini-daemon` without a simulation flag. For Wireless, power on the robot and follow the SDK guide to connect to its running daemon. Check that the microphone and speaker work and that the head and antennas have room to move.

Then run:

```bash
python -m ask_reachy.main --log-file ask_reachy/logs/study.jsonl
```

Each story has three storytelling responses, followed by a separate question asking whether the participant wants to continue. A turn ends after 5 seconds of quiet following detected speech. Short pauses inside a response count toward its duration; the final 5-second pause does not. If no speech starts within 90 seconds, the app records an empty turn and moves on.

You can press Enter to end a turn manually on supported terminals. This shortcut may not work in Windows terminals. Press **Ctrl+C once** to stop the session, and let the app return to neutral and finish writing its log.

Keep the recorded WAV files in `ask_reachy/ask_reachy/assets/` unchanged during the study. Also make sure `ASK_REACHY_SIMULATE_QUESTION` is not set to `1` when collecting real responses.

## Saved data

Each run adds one JSON record to the log file. Without `--log-file`, the default is `ask_reachy/logs/ask_reachy_runs.jsonl`.

The log includes the seed, condition order, completion status, response durations, transcripts, and Yes/No/Unclear continuation answers. It also marks whether the run used simulated responses. Participant IDs and questionnaire responses are not included, so keep a separate session sheet linking each participant to the run's `start_timestamp`. Note interruptions, repeated trials, and manual stops there too.

The app uses temporary audio files for transcription and does not keep them afterward. The saved JSON lets you repeat the log analysis, but not rerun speech recognition from the original audio.

## Reproducing the analysis

The repository does not currently include participant data or a completed analysis notebook. To reproduce numerical results, you will need the original study logs and session sheet. The example below shows how to summarize the data recorded by the app; it does not contain study results.

First, use the session sheet to choose one valid completed session per participant. Leave out pilot runs and handle interruptions or repeats according to the study's exclusion rules. Keep a record of these decisions. Copy the selected JSON lines into `ask_reachy/logs/analysis_input.jsonl`, keeping the original log unchanged.

For each condition, the example adds up the three storytelling response durations. It then compares Curious minus Shy within the same session. It also counts Yes, No, and Unclear continuation answers. The Yes rate is `Yes / (Yes + No)`, with Unclear reported separately.

Save this code as `analyze_logs.py` in the repository root. It only needs the Python standard library:

```python
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median, stdev

source = Path(sys.argv[1])
target = Path(sys.argv[2])
rows, differences = [], []
skipped = Counter()
seen = set()
for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
    if not line.strip():
        continue
    run = json.loads(line)
    if run.get("simulate_question") is not False:
        skipped["simulation or missing simulation flag"] += 1
        continue
    if run.get("completion_status") != "completed" or run.get("error"):
        skipped["incomplete or failed"] += 1
        continue
    if run.get("speech_played") is not True:
        skipped["no recorded playback"] += 1
        continue
    session = run["start_timestamp"]
    if session in seen:
        raise ValueError(f"Duplicate session timestamp at line {line_number}")
    seen.add(session)
    stories = run["stories"]
    assert len(stories) == 2, f"Expected two stories at line {line_number}"
    assert {s["characteristic"] for s in stories} == {"Shy", "Curious"}
    totals = {}
    for story in stories:
        turns = story["responses"]
        assert len(turns) == 3 and all(t["kind"] == "story" for t in turns)
        durations = [float(t["duration_s"]) for t in turns]
        assert all(0 <= d < float("inf") for d in durations)
        condition = story["characteristic"]
        answer = story.get("continue_answer") or "Unclear"
        assert answer in {"Yes", "No", "Unclear"}
        totals[condition] = sum(durations)
        rows.append({
            "session": session,
            "seed": run["seed"],
            "story_order": story["story"],
            "prompt": story["prompt"],
            "condition": condition,
            "narrative_duration_s": totals[condition],
            "continue_answer": answer,
            "transcription_errors": sum(bool(t.get("error")) for t in turns),
            "zero_duration_turns": sum(d == 0 for d in durations),
        })
    differences.append(totals["Curious"] - totals["Shy"])

print("Excluded sessions:", dict(skipped))
if not rows:
    raise SystemExit("No eligible sessions; no summary written.")
target.parent.mkdir(parents=True, exist_ok=True)
with target.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"Included paired sessions: {len(differences)}")
for condition in ("Shy", "Curious"):
    subset = [r for r in rows if r["condition"] == condition]
    values = [r["narrative_duration_s"] for r in subset]
    answers = Counter(r["continue_answer"] for r in subset)
    known = answers["Yes"] + answers["No"]
    rate = f"{answers['Yes'] / known:.1%}" if known else "N/A"
    sd = f"{stdev(values):.3f}s" if len(values) > 1 else "N/A"
    print(f"{condition}: n={len(values)}, mean={mean(values):.3f}s, "
          f"median={median(values):.3f}s, sample SD={sd}")
    print(f"  Yes={answers['Yes']}, No={answers['No']}, "
          f"Unclear={answers['Unclear']}; Yes/(Yes+No)={rate}")
print(f"Mean paired duration difference (Curious - Shy): {mean(differences):.3f}s")
print(f"Median paired duration difference: {median(differences):.3f}s")
print(f"Saved {target}")
```

Run it with:

```bash
python analyze_logs.py ask_reachy/logs/analysis_input.jsonl analysis/condition_summary.csv
```

This creates a CSV with two rows per included participant, one per condition. The terminal prints the mean, median, and sample standard deviation of total response duration, continuation counts, and the paired duration differences. A positive difference means the participant spoke longer in the Curious condition.

The script skips simulation and failed runs. Check zero-duration turns, transcription errors, and unclear continuation answers against the session sheet before interpreting the output. Automatic Yes/No labels use keyword matching and can miss the meaning of an answer. These are descriptive summaries, not significance tests. If you run a statistical test, keep the two conditions paired by participant and report the test and exclusion rules. Questionnaire analysis also needs the original questions and scoring rules.

To help someone repeat the analysis later, save the code revision and environment used:

```bash
git rev-parse HEAD
python --version
python -m pip freeze > environment-used.txt
```

Package versions are not pinned in this repository, so a fresh install may use different versions.

## Tests and common issues

Run the existing checks from the app folder:

```bash
cd ask_reachy
python -m unittest discover -s tests -p "test_*.py"
```

If the app cannot connect, check that the daemon is running. If using a different port, start the daemon with `--fastapi-port 8001` and add `--daemon-port 8001` to the app command.

If audio is unavailable, check the robot's media setup and make sure the daemon was not started with `--no-media`. Missing transcripts can also mean that the speech model could not load; check the terminal errors. Simulation checks the session flow and movement commands, but real microphone and speaker behavior still need to be checked on the robot.

More details about the script and movements are in [the app README](ask_reachy/README.md). The main session code is in `ask_reachy/ask_reachy/main.py`, with movement definitions in `choreography.py` and the fixed script in `speech.py`.
