"""Centralized logging for pipeline progress."""

from __future__ import annotations

import sys
import time


class PipelineLogger:
    """Logs pipeline progress to stderr with elapsed time."""

    def __init__(self):
        self._start = time.monotonic()
        self._stage_start: float | None = None

    def _elapsed(self) -> str:
        return f"{time.monotonic() - self._start:.1f}s"

    def info(self, message: str) -> None:
        sys.stderr.write(f"  [{self._elapsed()}] {message}\n")
        sys.stderr.flush()

    def stage_start(self, stage: str) -> None:
        self._stage_start = time.monotonic()
        sys.stderr.write(f"\n  {'='*50}\n")
        sys.stderr.write(f"  [{self._elapsed()}] ▶ {stage} 시작\n")
        sys.stderr.flush()

    def stage_end(self, stage: str, summary: str) -> None:
        duration = ""
        if self._stage_start is not None:
            duration = f" ({time.monotonic() - self._stage_start:.1f}s)"
        sys.stderr.write(f"  [{self._elapsed()}] ✓ {stage} 완료{duration} — {summary}\n")
        sys.stderr.flush()

    def progress(self, current: int, total: int, detail: str = "") -> None:
        pct = current / total * 100 if total > 0 else 0
        bar_len = 20
        filled = int(bar_len * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        msg = f"  [{self._elapsed()}]   {bar} {current}/{total} ({pct:.0f}%)"
        if detail:
            msg += f" {detail}"
        sys.stderr.write(f"\r{msg}")
        sys.stderr.flush()
        if current == total:
            sys.stderr.write("\n")


log = PipelineLogger()
