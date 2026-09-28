python - <<'PY'
from reachy_mini import ReachyMini
with ReachyMini() as mini:
mini.enable_motors()
print("Connected, moving antennas...")
mini.goto_target(
antennas=[0.3, -0.3],
duration=1.0
)
mini.goto_target(
antennas=[-0.3, 0.3],
duration=1.0
)
mini.goto_target(
antennas=[0.0, 0.0],
duration=1.0
)
print("Done")
PY