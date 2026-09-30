# Reachy Mini Local Configuration

## Setup Status
Setup complete: PARTIAL

The Reachy Mini SDK was already installed in the system Python (`reachy-mini` on Python 3.11.9). Example apps were not cloned into `~/reachy_mini_resources/` because this session built Ask Reachy directly in the lab repo. Robot type is not recorded yet.

## User Environment
- Robot type: unknown (tested in simulation only)
- OS: macOS
- Shell: zsh
- Python env tool: system Python 3.11.9 (uv is installed but was not required)
- Resources path: not created
- App path: ask_reachy/ inside this lab repo

## Notes for Future Sessions
- Ask Reachy is a local Python app. It was not published to Hugging Face. The lab git repo is the copy of record.
- One session runs both stories. Shy is `motion_energy` 0.25. Curious is `motion_energy` 0.90. The program shuffles prompt order and which style pairs with which prompt, and prints the seed.
- Spoken lines are fixed WAVs in `ask_reachy/ask_reachy/assets/` (`intro`, `prompt_a`, `prompt_b`, `whats_next`, `continue_expanding`, `end_story_1`, `end_story_2`, `study_closing`). Do not regenerate them mid-study.
- A participant turn ends after 5 seconds of quiet. Length prints immediately. Transcripts use local faster-whisper and must not block the next line. Yes/No does not change the goodbye.
- Neutral pose is head identity, antennas `[0, 0]` rad, body yaw 0. Start and end both use that pose.
- Simulation was run with `reachy-mini-daemon --mockup-sim` or `--sim`. Audio in/out still needs the physical robot.
