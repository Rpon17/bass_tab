from __future__ import annotations

import json
from dataclasses import dataclass
from math import inf
from pathlib import Path
from typing import Any

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.onset.onset_json_noramization_port import (
    OnsetNormalizeParams,
    OnsetNormalizePort,
)


@dataclass(frozen=True)
class OnsetPitchOctaveNormalizeAdapter(OnsetNormalizePort):
    """
    onset_note (note event) 기준 Viterbi 옥타브 정규화.

    - 입력/출력: BasicPitchNoteEventDTO (start_time, end_time, pitch_midi, confidence)
    - 전처리: start_time 기준 sort -> pitch_low 미만은 +12 lift
    - Viterbi: alias_semitones 후보 오프셋 중 비용 최소 경로 선택
    - 후처리: pitch_low 미만은 +12 재적용 + midi_min/max clamp
    """

    pitch_low: int = 40
    output_filename: str = "onset_note_octave_normalized.json"

    def normalize(
        self,
        *,
        notes: list[BasicPitchNoteEventDTO],
        params: OnsetNormalizeParams,
    ) -> list[BasicPitchNoteEventDTO]:
        if not notes:
            return []

        # (0) 전처리: sort -> lift(<pitch_low => +12)
        notes_sorted: list[BasicPitchNoteEventDTO] = self._sort_notes(notes=notes)


        notes_in: list[BasicPitchNoteEventDTO] = notes_sorted

        # alias 후보 offsets
        offsets: list[int] = [int(k) for k in params.alias_semitones]
        if 0 not in offsets:
            offsets = [0] + offsets

        S: int = int(len(offsets))
        T: int = int(len(notes_in))

        # DP tables
        prev_idx: list[list[int]] = [[-1] * S for _ in range(T)]
        prev_cost: list[float] = [inf] * S
        cur_cost: list[float] = [inf] * S

        # ---- t=0 초기화 ----
        conf0: float | None = notes_in[0].confidence
        for s in range(S):
            prev_cost[s] = float(
                self._emission_cost_offset(
                    offset=int(offsets[s]),
                    obs_conf=conf0,
                    params=params,
                )
            )
            prev_idx[0][s] = -1

        # ---- DP ----
        for t in range(1, T):
            obs_pitch: int = int(notes_in[t].pitch_midi)
            obs_conf: float | None = notes_in[t].confidence

            emit_costs: list[float] = [
                float(
                    self._emission_cost_offset(
                        offset=int(k),
                        obs_conf=obs_conf,
                        params=params,
                    )
                )
                for k in offsets
            ]

            prev_obs_pitch: int = int(notes_in[t - 1].pitch_midi)

            for s in range(S):
                best_cost: float = inf
                best_pi: int = -1

                cur_pitch: int = int(obs_pitch + int(offsets[s]))

                for p in range(S):
                    prev_pitch: int = int(prev_obs_pitch + int(offsets[p]))
                    trans: float = float(
                        self._transition_cost(
                            prev_pitch=int(prev_pitch),
                            cur_pitch=int(cur_pitch),
                            params=params,
                        )
                    )
                    c: float = float(prev_cost[p]) + float(trans)
                    if c < best_cost:
                        best_cost = float(c)
                        best_pi = int(p)

                cur_cost[s] = float(best_cost) + float(emit_costs[s])
                prev_idx[t][s] = int(best_pi)

            prev_cost, cur_cost = cur_cost, [inf] * S

        # ---- backtrace ----
        last_state: int = int(min(range(S), key=lambda i: float(prev_cost[i])))
        path_state_idx: list[int] = [0] * T
        path_state_idx[T - 1] = int(last_state)

        for t in range(T - 1, 0, -1):
            path_state_idx[t - 1] = int(prev_idx[t][path_state_idx[t]])

        # ---- 적용 ----
        midi_min: int = int(params.midi_min)
        midi_max: int = int(params.midi_max)

        out: list[BasicPitchNoteEventDTO] = []
        for t in range(T):
            base_pitch: int = int(notes_in[t].pitch_midi)
            best_offset: int = int(offsets[path_state_idx[t]])
            st_pitch: int = int(base_pitch + best_offset)

            if st_pitch < midi_min:
                st_pitch = int(midi_min)
            if st_pitch > midi_max:
                st_pitch = int(midi_max)

            n: BasicPitchNoteEventDTO = notes_in[t]
            out.append(
                BasicPitchNoteEventDTO(
                    start_time=float(n.start_time),
                    end_time=float(n.end_time),
                    pitch_midi=int(st_pitch),
                    confidence=None if n.confidence is None else float(n.confidence),
                )
            )

        return self._sort_notes(notes=out)

    def normalize_file(
        self,
        *,
        input_json_path: Path,
        output_dir: Path,
        params: OnsetNormalizeParams,
        overwrite: bool = True,
    ) -> Path:
        if not input_json_path.exists():
            raise FileNotFoundError(f"input not found: {input_json_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path: Path = output_dir / self.output_filename

        if output_path.exists() and not overwrite:
            raise FileExistsError(f"output already exists: {output_dir}")

        with input_json_path.open("r", encoding="utf-8") as f:
            raw_obj: object = json.load(f)

        notes_raw: list[BasicPitchNoteEventDTO] = self._parse_notes_json(raw_obj)

        out_notes: list[BasicPitchNoteEventDTO] = self.normalize(
            notes=notes_raw,
            params=params,
        )

        payload: list[dict[str, Any]] = [
            {
                "start_time": float(n.start_time),
                "end_time": float(n.end_time),
                "pitch_midi": int(n.pitch_midi),
                "confidence": None if n.confidence is None else float(n.confidence),
            }
            for n in out_notes
        ]

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            
        return output_path

    # ------------------------
    # helpers: sort / lift
    # ------------------------
    @staticmethod
    def _sort_notes(*, notes: list[BasicPitchNoteEventDTO]) -> list[BasicPitchNoteEventDTO]:
        return sorted(
            notes,
            key=lambda n: (
                float(n.start_time),
                float(n.end_time),
                int(n.pitch_midi),
                -1.0 if n.confidence is None else -float(n.confidence),
            ),
        )

    @staticmethod
    def _lift_one_pitch_below_midi(*, pitch_midi: int, midi_floor: int) -> int:
        p: int = int(pitch_midi)
        floor: int = int(midi_floor)
        if p < floor:
            p += 12
        return int(p)

    # ------------------------
    # emission / transition
    # ------------------------
    @staticmethod
    def _clamp_float(*, x: float, lo: float, hi: float) -> float:
        if x < lo:
            return float(lo)
        if x > hi:
            return float(hi)
        return float(x)

    def _emission_cost_offset(
        self,
        *,
        offset: int,
        obs_conf: float | None,
        params: OnsetNormalizeParams,
    ) -> float:
        conf_floor: float = float(params.conf_floor)
        conf_power: float = float(params.conf_power)
        conf_default: float = float(params.conf_default)
        conf_cost: float = float(params.conf_cost)

        c: float = float(conf_floor if obs_conf is None else float(obs_conf))
        c = float(self._clamp_float(x=float(c), lo=float(conf_floor), hi=1.0))
        conf_w: float = float(c**conf_power)

        octs: int = abs(int(offset)) // 12
        alias_pen: float = float(octs) * float(params.alias_cost_per_octave)
        return float(alias_pen) * (float(conf_default) + float(conf_cost) * float(conf_w))

    @staticmethod
    def _transition_cost(
        *,
        prev_pitch: int,
        cur_pitch: int,
        params: OnsetNormalizeParams,
    ) -> float:
        dp: int = abs(int(cur_pitch) - int(prev_pitch))

        # ✅ 보편성 관점:
        # 노트 이벤트는 프레임보다 점프가 자연스러운 경우가 많아서 dp 그대로 벌점주면 과벌점 가능.
        # 최소한 12로 캡핑하면, "일반적인 진행"을 덜 망가뜨리면서도 급격한 튐은 억제 가능.
        step_cost: float = float(params.lambda_step) * float(min(dp, 12))

        is_oct_like: bool = (dp % 12 == 0)
        oct_cost: float = float(params.lambda_oct) if is_oct_like else 0.0
        return float(step_cost + oct_cost)

    # ------------------------
    # json parsing
    # ------------------------
    @staticmethod
    def _parse_notes_json(obj: object) -> list[BasicPitchNoteEventDTO]:
        if not isinstance(obj, list):
            raise ValueError("notes json must be a list of objects")

        out: list[BasicPitchNoteEventDTO] = []
        for i, row_obj in enumerate(obj):
            if not isinstance(row_obj, dict):
                raise ValueError(f"notes[{i}] must be an object")

            st_obj: object = row_obj.get("start_time", row_obj.get("start"))
            et_obj: object = row_obj.get("end_time", row_obj.get("end"))
            pitch_obj: object = row_obj.get("pitch_midi", row_obj.get("pitch"))
            conf_obj: object = row_obj.get("confidence", row_obj.get("conf"))

            if st_obj is None or et_obj is None or pitch_obj is None:
                raise ValueError(
                    f"notes[{i}] missing required keys: start_time, end_time, pitch_midi"
                )

            out.append(
                BasicPitchNoteEventDTO(
                    start_time=float(st_obj),
                    end_time=float(et_obj),
                    pitch_midi=int(pitch_obj),
                    confidence=None if conf_obj is None else float(conf_obj),
                )
            )

        return out