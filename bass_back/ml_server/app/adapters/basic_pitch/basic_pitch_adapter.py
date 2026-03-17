from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import basic_pitch.constants as c
import numpy as np

from app.application.ports.basic_pitch.basic_pitch_port import (
    BasicPitchFramePitchDTO,
    BasicPitchNoteEventDTO,
    BasicPitchParams,
    BasicPitchPort,
    BasicPitchResult,
)


@dataclass(frozen=True)
class BasicPitchAdapter(BasicPitchPort):
    async def export_onset(
        self,
        *,
        params: BasicPitchParams,
    ) -> list[BasicPitchNoteEventDTO]:
        input_wav_path: Path = params.input_wav_path

        model_output: Mapping[str, Any]
        note_events_obj: object
        model_output, note_events_obj = await self._predict_basic_pitch(
            input_wav_path=input_wav_path,
        )
        _ = model_output

        note_events: list[BasicPitchNoteEventDTO] = _extract_note_events(note_events_obj)
        print("basic_pitcg로 온셋 리스트 추출완료")
        return note_events

    async def export_frame(
        self,
        *,
        params: BasicPitchParams,
    ) -> list[BasicPitchFramePitchDTO]:
        input_wav_path: Path = params.input_wav_path

        model_output: Mapping[str, Any]
        note_events_obj: object
        model_output, note_events_obj = await self._predict_basic_pitch(
            input_wav_path=input_wav_path,
        )
        _ = note_events_obj

        frame_source: str = getattr(params, "frame_source", "notes")

        picked: tuple[str, np.ndarray] | None = _pick_frame_array(
            model_output=model_output,
            frame_source=frame_source,
        )
        if picked is None:
            return []

        _picked_key: str
        arr: np.ndarray
        _picked_key, arr = picked

        time_pitch: np.ndarray | None = _normalize_time_pitch_matrix(arr=arr)
        if time_pitch is None:
            return []

        consts: dict[str, float] = _get_basic_pitch_constants()
        frame_times: np.ndarray = _build_frame_times(
            num_frames=int(time_pitch.shape[0]),
            fps=float(consts["fps"]),
        )

        conf_threshold: float = float(params.frame_conf_threshold)

        frame_pitches: list[BasicPitchFramePitchDTO] = _extract_frame_pitches(
            time_pitch=time_pitch,
            frame_times=frame_times,
            conf_threshold=conf_threshold,
            midi_offset=float(consts["midi_offset"]),
            bins_per_semitone=float(consts["bins_per_semitone"]),
        )
        print("basic_pitch로  리스트 추출완료")
        return frame_pitches

    async def export_file(
        self,
        *,
        params: BasicPitchParams,
    ) -> BasicPitchResult:
        output_dir: Path = params.output_dir

        note_events_path: Path = (
            output_dir / "assets" / params.asset_id / params.note_events_filename
        )
        frame_pitches_path: Path = (
            output_dir / "assets" / params.asset_id / params.frame_pitches_filename
        )

        if not params.overwrite:
            if note_events_path.exists() and frame_pitches_path.exists():
                return BasicPitchResult(
                    note_events_json_path=note_events_path,
                    frame_pitches_json_path=frame_pitches_path,
                )

        note_events: list[BasicPitchNoteEventDTO] = await self.export_onset(
            params=params,
        )
        frame_pitches: list[BasicPitchFramePitchDTO] = await self.export_frame(
            params=params,
        )

        note_payload: list[dict[str, Any]] = [
            {
                "start_time": float(e.start_time),
                "end_time": float(e.end_time),
                "pitch_midi": int(e.pitch_midi),
                "confidence": None if e.confidence is None else float(e.confidence),
            }
            for e in note_events
        ]

        frame_payload: list[dict[str, Any]] = [
            {
                "t": float(fp.t),
                "pitch_midi": int(fp.pitch_midi),
                "confidence": None if fp.confidence is None else float(fp.confidence),
            }
            for fp in frame_pitches
        ]

        _json_dump(path=note_events_path, payload=note_payload)
        _json_dump(path=frame_pitches_path, payload=frame_payload)

        return BasicPitchResult(
            note_events_json_path=note_events_path,
            frame_pitches_json_path=frame_pitches_path,
        )

    async def _predict_basic_pitch(
        self,
        *,
        input_wav_path: Path,
    ) -> tuple[Mapping[str, Any], object]:
        if not input_wav_path.exists():
            raise FileNotFoundError(f"input wav not found: {input_wav_path}")

        from basic_pitch.inference import predict

        def _run_predict() -> tuple[Mapping[str, Any], Any, Any]:
            return predict(str(input_wav_path))

        model_output: Mapping[str, Any]
        _midi_data: Any
        note_events_obj: object
        model_output, _midi_data, note_events_obj = await asyncio.to_thread(_run_predict)

        return model_output, note_events_obj


def _get_basic_pitch_constants() -> dict[str, float]:
    return {
        "fps": float(c.ANNOTATIONS_FPS),
        "bins_per_semitone": float(c.NOTES_BINS_PER_SEMITONE),
        "midi_offset": 21.0,
    }


def _json_dump(*, path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path: Path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    tmp_path.replace(path)


def _iter_note_rows(note_events_obj: object) -> Iterable[dict[str, Any]]:
    if isinstance(note_events_obj, list):
        for r in note_events_obj:
            if isinstance(r, dict):
                yield r
                continue

            start_time: object = getattr(r, "start_time", None)
            end_time: object = getattr(r, "end_time", None)

            pitch: object = getattr(r, "pitch_midi", None)
            if pitch is None:
                pitch = getattr(r, "pitch", None)

            confidence: object = getattr(r, "confidence", None)

            if start_time is not None and end_time is not None and pitch is not None:
                yield {
                    "start_time": start_time,
                    "end_time": end_time,
                    "pitch": pitch,
                    "confidence": confidence,
                }
        return

    if isinstance(note_events_obj, dict):
        for k in ("note_events", "notes", "events"):
            v: object = note_events_obj.get(k)
            if isinstance(v, list):
                for r in v:
                    if isinstance(r, dict):
                        yield r
                    else:
                        start_time: object = getattr(r, "start_time", None)
                        end_time: object = getattr(r, "end_time", None)

                        pitch: object = getattr(r, "pitch_midi", None)
                        if pitch is None:
                            pitch = getattr(r, "pitch", None)

                        confidence: object = getattr(r, "confidence", None)

                        if (
                            start_time is not None
                            and end_time is not None
                            and pitch is not None
                        ):
                            yield {
                                "start_time": start_time,
                                "end_time": end_time,
                                "pitch": pitch,
                                "confidence": confidence,
                            }
                return

    return


def _extract_note_events(note_events_obj: object) -> list[BasicPitchNoteEventDTO]:
    out: list[BasicPitchNoteEventDTO] = []

    if not isinstance(note_events_obj, list):
        return out

    for e in note_events_obj:
        start_time: float | None = None
        end_time: float | None = None
        pitch_midi: int | None = None
        confidence: float | None = None

        if isinstance(e, tuple):
            if len(e) < 3:
                continue

            start_time = float(e[0])
            end_time = float(e[1])
            pitch_midi = int(round(float(e[2])))

            if len(e) >= 4:
                try:
                    confidence = float(e[3])
                except Exception:
                    confidence = None

        elif isinstance(e, dict):
            start_time = float(e.get("start_time", e.get("start", 0.0)))
            end_time = float(e.get("end_time", e.get("end", 0.0)))
            pitch_midi = int(round(float(e.get("pitch", e.get("pitch_midi", 0)))))

            conf_obj: object = e.get("confidence", e.get("conf", None))
            if conf_obj is not None:
                try:
                    confidence = float(conf_obj)
                except Exception:
                    confidence = None

        else:
            st: object = getattr(e, "start_time", None)
            et: object = getattr(e, "end_time", None)

            p: object = getattr(e, "pitch_midi", None)
            if p is None:
                p = getattr(e, "pitch", None)

            conf_obj2: object = getattr(e, "confidence", None)

            if st is None or et is None or p is None:
                continue

            start_time = float(st)
            end_time = float(et)
            pitch_midi = int(round(float(p)))

            if conf_obj2 is not None:
                try:
                    confidence = float(conf_obj2)
                except Exception:
                    confidence = None

        if start_time is None or end_time is None or pitch_midi is None:
            continue

        if end_time <= start_time:
            continue

        out.append(
            BasicPitchNoteEventDTO(
                start_time=start_time,
                end_time=end_time,
                pitch_midi=pitch_midi,
                confidence=confidence,
            )
        )

    return out


def _bin_to_midi(*, bin_index: int, midi_offset: float, bins_per_semitone: float) -> int:
    midi_float: float = midi_offset + (float(bin_index) / float(bins_per_semitone))
    return int(round(midi_float))


def _pick_frame_array(
    *,
    model_output: Mapping[str, Any],
    frame_source: str = "notes",
) -> tuple[str, np.ndarray] | None:
    key_alias: dict[str, tuple[str, ...]] = {
        "notes": ("notes", "note"),
        "contours": ("contours", "contour"),
    }

    def get_arr(key: str) -> np.ndarray | None:
        v: object = model_output.get(key)

        if isinstance(v, np.ndarray):
            return v

        to_numpy = getattr(v, "numpy", None)
        if callable(to_numpy):
            try:
                arr: object = to_numpy()
                if isinstance(arr, np.ndarray):
                    return arr
            except Exception:
                return None

        return None

    for k in key_alias.get(frame_source, ()):
        arr: np.ndarray | None = get_arr(k)
        if arr is not None:
            return (k, arr)

    return None


def _normalize_time_pitch_matrix(*, arr: np.ndarray) -> np.ndarray | None:
    if arr.ndim != 2:
        return None

    if arr.shape[0] >= arr.shape[1]:
        return arr

    return arr.T


def _build_frame_times(*, num_frames: int, fps: float) -> np.ndarray:
    if num_frames <= 0:
        return np.zeros((0,), dtype=np.float64)

    return np.arange(num_frames, dtype=np.float64) / float(fps)


def _extract_frame_pitches(
    *,
    time_pitch: np.ndarray,
    frame_times: np.ndarray,
    conf_threshold: float,
    midi_offset: float,
    bins_per_semitone: float,
) -> list[BasicPitchFramePitchDTO]:
    T: int = int(min(time_pitch.shape[0], frame_times.shape[0]))

    top_idx: np.ndarray = np.argmax(time_pitch[:T], axis=1)
    top_val: np.ndarray = np.max(time_pitch[:T], axis=1)

    out: list[BasicPitchFramePitchDTO] = []
    for i in range(T):
        conf: float = float(top_val[i])
        if conf < conf_threshold:
            continue

        pitch_midi: int = _bin_to_midi(
            bin_index=int(top_idx[i]),
            midi_offset=midi_offset,
            bins_per_semitone=bins_per_semitone,
        )

        out.append(
            BasicPitchFramePitchDTO(
                t=float(frame_times[i]),
                pitch_midi=pitch_midi,
                confidence=conf,
            )
        )
    return out