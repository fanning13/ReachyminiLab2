"""One JSON record per Ask Reachy run."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = (
    Path(__file__).resolve().parent.parent / "logs" / "ask_reachy_runs.jsonl"
)


def iso_now() -> str:
    """Local timestamp with milliseconds, for the study log."""
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def write_run_record(record: dict[str, Any], path: Path | None = None) -> Path:
    """Append one run record as a single JSON line. Returns the log path."""
    log_path = path or DEFAULT_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return log_path
