from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OnsetOnlySortAdapter:
    output_filename: str = "onset_only_sort.json"

    def normalize_file(
        self,
        *,
        input_json_path: Path,
        output_dir: Path,
        overwrite: bool = True,
    ) -> Path:
        if not input_json_path.exists():
            raise FileNotFoundError(f"input not found: {input_json_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path: Path = output_dir / self.output_filename
        if output_path.exists() and not overwrite:
            return output_path

        raw: Any = json.loads(input_json_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("notes json must be a list")

        # ✅ sort만: start_time -> end_time 순
        raw_sorted: list[dict[str, Any]] = sorted(
            (x for x in raw if isinstance(x, dict) and "start_time" in x and "end_time" in x),
            key=lambda d: (float(d["start_time"]), float(d["end_time"])),
        )

        output_path.write_text(
            json.dumps(raw_sorted, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path