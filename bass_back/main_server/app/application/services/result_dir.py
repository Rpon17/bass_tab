# app/application/services/job_workspace.py
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class JobWorkspace:
    output_dir: Path
    audio_dir: Path
    tab_dir: Path

def workspace_from_output_dir(*, output_dir: Path) -> JobWorkspace:
    return JobWorkspace(
        output_dir=output_dir,
        audio_dir=output_dir / "audio",
        tab_dir=output_dir / "tab",
    )
