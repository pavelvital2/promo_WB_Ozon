from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class StoragePathBuilder:
    root_path: Path

    def temp_uploads_dir(self) -> Path:
        return self.root_path / "uploads" / "tmp"

    def run_dir(self, module_code: str, store_id: int | str, public_run_number: str) -> Path:
        return self.root_path / "runs" / module_code / str(store_id) / public_run_number

    def run_input_dir(self, module_code: str, store_id: int | str, public_run_number: str) -> Path:
        return self.run_dir(module_code, store_id, public_run_number) / "input"

    def run_output_dir(self, module_code: str, store_id: int | str, public_run_number: str) -> Path:
        return self.run_dir(module_code, store_id, public_run_number) / "output"

