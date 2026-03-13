from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.application.ports.tab.frame.frame_note_normalization_port import FramePitchNormalizeParams


def load_frame_list(*, input_json_path: Path) -> list[dict[str, Any]]:
    raw: Any = json.loads(input_json_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"input must be list json: {input_json_path}")

    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        if "t" not in item:
            continue

        t: float = float(item.get("t"))
        pitch_obj: object = item.get("pitch_midi", item.get("pitch", None))
        if pitch_obj is None:
            continue
        pitch_midi: int = int(pitch_obj)

        conf_obj: object = item.get("confidence", item.get("conf", None))
        confidence: float | None = None if conf_obj is None else float(conf_obj)

        out.append({"t": t, "pitch_midi": pitch_midi, "confidence": confidence})

    return out


def sort_by_time(*, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(frames, key=lambda r: float(r["start_time"]))


def confidence_cut(
    *,
    frames: list[dict[str, Any]],
    conf_threshold: float,
) -> list[dict[str, Any]]:
    return [
        {
            "t": float(f["t"]),
            "pitch_midi": int(f["pitch_midi"]),
            "confidence": float(f["confidence"]),
        }
        for f in frames
        if f.get("confidence") is not None and float(f["confidence"]) >= conf_threshold
    ]


def save_json(*, output_json_path: Path, data: list[dict[str, Any]]) -> None:
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run(
    *,
    input_json_path: Path,
    output_dir: Path,
    output_filename: str = "onset_sorted_conf_cut.json",
    params: FramePitchNormalizeParams,
) -> Path:
    frames: list[dict[str, Any]] = load_frame_list(input_json_path=input_json_path)
    frames_sorted: list[dict[str, Any]] = sort_by_time(frames=frames)
    frames_cut: list[dict[str, Any]] = confidence_cut(
        frames=frames_sorted,
        conf_threshold=float(params.conf_threshold),
    )

    out_path: Path = output_dir / output_filename
    save_json(output_json_path=out_path, data=frames_cut)

    print(f"input frames: {len(frames)}")
    print(f"after sort:   {len(frames_sorted)}")
    print(f"after cut:    {len(frames_cut)}")
    print(f"saved to:     {out_path}")
    print(f"conf:         {float(params.conf_threshold)}")
    print("params type:", type(params), params)
    
    return out_path


if __name__ == "__main__":
    input_json_path: Path = Path(
        r"C:\bass_project\storage\basic_pitch\test1\assets\test_asset_001\note_events.json"
    )
    output_dir: Path = Path(r"C:\bass_project\storage\frame_sort")
    params: FramePitchNormalizeParams = FramePitchNormalizeParams(conf_threshold=0.4)
    run(
        input_json_path=input_json_path,
        output_dir=output_dir,
        params=params,
    )