from __future__ import annotations

import json
from dataclasses import dataclass
from math import inf
from pathlib import Path
from typing import Any

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchFramePitchDTO
from app.application.ports.tab.frame.frame_octave_port import (
    FramePitchOctaveNormalizeParams,
    FramePitchOctaveNormalizePort,
)


@dataclass(frozen=True)
class FramePitchOctaveNormalizeAdapter(FramePitchOctaveNormalizePort):
    output_filename: str = "frame_pitch_octave_normalized.json"

    """
    HMM -> 숨겨진상태, 실제관측값을 마르코프적으로 Viterbi로 해결
    Emission -> 관측한 pitch 및 alias(옥타브) 오프셋에 비용 부여
    Transition -> 연속성 비용 + 옥타브 점프 추가 비용

    총점 = transition(연속성/점프 비용) + emission(관측과의 일치 비용)
    """

    def normalize(
        self,
        *,
        frames: list[BasicPitchFramePitchDTO],
        params: FramePitchOctaveNormalizeParams,
    ) -> list[BasicPitchFramePitchDTO]:
        if not frames:
            return []

        offsets: list[int] = [int(k) for k in params.alias_semitones]
        if 0 not in offsets:
            offsets = [0] + offsets

        S: int = len(offsets)
        T: int = len(frames)

        prev_idx: list[list[int]] = [[-1] * S for _ in range(T)]
        prev_cost: list[float] = [inf] * S
        cur_cost: list[float] = [inf] * S

        conf0: float | None = frames[0].confidence
        for s in range(S):
            prev_cost[s] = self._emission_cost_offset(
                offset=offsets[s],
                obs_conf=conf0,
                params=params,
            )
            prev_idx[0][s] = -1

        for t in range(1, T):
            obs_pitch: int = frames[t].pitch_midi
            obs_conf: float | None = frames[t].confidence

            cur_state_pitches: list[int] = [obs_pitch + k for k in offsets]

            emit_costs: list[float] = [
                self._emission_cost_offset(
                    offset=k,
                    obs_conf=obs_conf,
                    params=params,
                )
                for k in offsets
            ]

            prev_obs_pitch: int = frames[t - 1].pitch_midi

            for s in range(S):
                best_cost: float = inf
                best_pi: int = -1

                cur_pitch: int = cur_state_pitches[s]

                for p in range(S):
                    prev_pitch: int = prev_obs_pitch + offsets[p]

                    trans: float = self._transition_cost(
                        prev_pitch=prev_pitch,
                        cur_pitch=cur_pitch,
                        params=params,
                    )

                    c: float = prev_cost[p] + trans

                    if c < best_cost:
                        best_cost = c
                        best_pi = p

                cur_cost[s] = best_cost + emit_costs[s]
                prev_idx[t][s] = best_pi

            prev_cost, cur_cost = cur_cost, [inf] * S

        last_state: int = min(range(S), key=lambda i: prev_cost[i])

        path_state_idx: list[int] = [0] * T
        path_state_idx[T - 1] = last_state

        for t in range(T - 1, 0, -1):
            path_state_idx[t - 1] = prev_idx[t][path_state_idx[t]]

        midi_min: int = params.midi_min
        midi_max: int = params.midi_max

        out: list[BasicPitchFramePitchDTO] = []

        for t in range(T):
            obs_pitch: int = frames[t].pitch_midi
            best_offset: int = offsets[path_state_idx[t]]

            st_pitch: int = obs_pitch + best_offset

            if st_pitch < midi_min:
                st_pitch = midi_min

            if st_pitch > midi_max:
                st_pitch = midi_max

            f: BasicPitchFramePitchDTO = frames[t]

            out.append(
                BasicPitchFramePitchDTO(
                    t=float(f.t),
                    pitch_midi=int(st_pitch),
                    confidence=f.confidence,
                )
            )

        return out

    def normalize_file(
        self,
        *,
        input_json_path: Path,
        output_dir: Path,
        params: FramePitchOctaveNormalizeParams,
        overwrite: bool = True,
    ) -> Path:
        if not input_json_path.exists():
            raise FileNotFoundError(f"input not found: {input_json_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path: Path = output_dir / self.output_filename

        if output_path.exists() and not overwrite:
            return output_path

        raw_obj: object
        with input_json_path.open("r", encoding="utf-8") as f:
            raw_obj = json.load(f)

        frames_raw: list[BasicPitchFramePitchDTO] = self._parse_frames_json(raw_obj)

        out_frames: list[BasicPitchFramePitchDTO] = self.normalize(
            frames=frames_raw,
            params=params,
        )

        payload: list[dict[str, Any]] = [
            {
                "t": float(fr.t),
                "pitch_midi": int(fr.pitch_midi),
                "confidence": None if fr.confidence is None else float(fr.confidence),
            }
            for fr in out_frames
        ]

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return output_path

    # json parsing
    @staticmethod
    def _parse_frames_json(obj: object) -> list[BasicPitchFramePitchDTO]:
        if not isinstance(obj, list):
            raise ValueError("frames json must be a list of objects")

        out: list[BasicPitchFramePitchDTO] = []
        for i, row_obj in enumerate(obj):
            if not isinstance(row_obj, dict):
                raise ValueError(f"frames[{i}] must be an object")

            t_obj: object = row_obj.get("t")
            pitch_obj: object = row_obj.get("pitch_midi", row_obj.get("pitch"))
            conf_obj: object = row_obj.get("confidence", row_obj.get("conf"))

            if t_obj is None or pitch_obj is None:
                raise ValueError(f"frames[{i}] missing required keys: t, pitch_midi")

            t: float = float(t_obj)
            pitch_midi: int = int(pitch_obj)
            confidence: float | None = None if conf_obj is None else float(conf_obj)

            out.append(
                BasicPitchFramePitchDTO(
                    t=float(t),
                    pitch_midi=int(pitch_midi),
                    confidence=None if confidence is None else float(confidence),
                )
            )

        return out

    def _emission_cost_offset(
        self,
        *,
        offset: int,
        obs_conf: float | None,
        params: FramePitchOctaveNormalizeParams,
    ) -> float:
        conf_floor: float = params.conf_floor
        conf_power: float = params.conf_power
        conf_default: float = params.conf_default
        conf_cost: float = params.conf_cost

        c: float = conf_floor if obs_conf is None else float(obs_conf)

        if c < conf_floor:
            c = conf_floor
        if c > 1.0:
            c = 1.0

        conf_w: float = c ** conf_power

        octs: int = abs(offset) // 12
        alias_pen: float = octs * params.alias_cost_per_octave

        return alias_pen * (conf_default + conf_cost * conf_w)

    def _transition_cost(
        self,
        *,
        prev_pitch: int,
        cur_pitch: int,
        params: FramePitchOctaveNormalizeParams,
    ) -> float:
        dp: int = abs(cur_pitch - prev_pitch)

        # 보편적으로 너무 큰 dp를 그대로 벌점주면 과하게 고정될 수 있어서 캡핑
        step_cost: float = params.lambda_step * min(dp, 12)

        is_oct_like: bool = (dp % 12 == 0)
        oct_cost: float = params.lambda_oct if is_oct_like else 0.0

        return step_cost + oct_cost