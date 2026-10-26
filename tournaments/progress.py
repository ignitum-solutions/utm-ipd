"""Per-tournament progress hooks for the pinned Axelrod 4.13 engine.

No global tqdm or random-state patches. Each unit is one completed player-pair
chunk, including its repetitions. Numerical execution remains Axelrod's own.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import axelrod as axl


class ProgressTournament(axl.Tournament):
    def __init__(self, *args, progress_callback=None, checkpoint=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.progress_callback: Callable[[int, int], None] | None = progress_callback
        self.checkpoint = checkpoint or (lambda: None)
        self.completed_chunks = 0

    def _play_matches(self, chunk, build_results=True):
        self.checkpoint()
        result = super()._play_matches(chunk, build_results=build_results)
        self.checkpoint()
        self.completed_chunks += 1
        if self.progress_callback:
            self.progress_callback(self.completed_chunks, self.match_generator.size)
        return result

    def play(self, *args, **kwargs):
        self.completed_chunks = 0
        try:
            return super().play(*args, **kwargs)
        except BaseException:
            # Axelrod cleans its temporary CSV only on successful completion.
            descriptor = getattr(self, "_temp_file_descriptor", None)
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                if self.filename:
                    Path(self.filename).unlink(missing_ok=True)
            raise
