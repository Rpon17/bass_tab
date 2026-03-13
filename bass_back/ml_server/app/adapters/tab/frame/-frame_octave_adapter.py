from __future__ import annotations

import json
from typing import Any
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import inf
from typing import Iterable

from app.application.ports.tab.frame.frame_octave_port import FramePitchOctaveNormalizeParams,FramePitchOctaveNormalizePort
from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchFramePitchDTO

@dataclass(frozen=True)
class ViterbiFramePitchOctaveNormalizeAdapter(FramePitchOctaveNormalizePort):
    """
    HMM -> 숨겨진상태 , 실제관측값 이를 마르코프 적인 방법인 Viterbi로 해결함
    Emission -> 관측한 pitch및 옥타브 차이에 질량을 분배함
    Transition ->  연속성 비용 그리고 옥타브 점프에 추가 비용
    
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
        
        midi_min: int = int(params.midi_min)
        midi_max: int = int(params.midi_max)
        if midi_max < midi_min:
            raise ValueError("midi_max must be >= midi_min")
        
        # 후보들을 만듬
        states: list[int] = list(range(midi_min, midi_max + 1)) # 프레임 후보들
        S: int = len(states) # 피치 후보 길이 여기서는 55로 고정됨
        T: int = len(frames) # 프레임의 전체 길이 = 시간


        # DP 테이블: prev index(백포인터) + 누적 비용
        # cost[t][s]는 크니까 2줄 롤링으로
        prev_idx: list[list[int]] = [[-1] * S for _ in range(T)] # prev_idx [t][s]
        """  
            prev_idx =
            [
                [-1, -1, -1],   # t=0
                [-1, -1, -1],   # t=1
                [-1, -1, -1],   # t=2
                [-1, -1, -1]    # t=3
            ]
        """
        prev_cost: list[float] = [inf] * S # t-1까지의 누적비용
        cur_cost: list[float] = [inf] * S # t까지의 누적비용


        # t=0 초기화
        pitch0: int = int(frames[0].pitch_midi)
        conf0: float | None = frames[0].confidence
        
        # prev_cost -> emission값이 얼마인지 
        # prev_cost에는 emission_cost한 값을 넣는다
        
        # prev_idx -> 이전에 어디서 왔으면 가장 비용이 적었는지
        # prev_idx는 다 -1로 채운다
        
        """  
            최초 prev_cost를 만들고 최초 prev_idx를 만든다
        """
        for st_idx, st_pitch in enumerate(states):
            prev_cost[st_idx] = self._emission_cost(
                state_pitch=int(st_pitch),
                obs_pitch=int(pitch0),
                obs_conf=float(conf0),
                params=params,
            )
            prev_idx[0][st_idx] = -1

        # 각 t별로 루프
        for t in range(1, T):
            obs_pitch: int = int(frames[t].pitch_midi) # 실제 pitch
            obs_conf: float | None = frames[t].confidence #실제 confidence

            # emit_costs에는 state별로의 emission한 값들이 들어간다
            emit_costs: list[float] = [
                self._emission_cost(
                    state_pitch=int(st_pitch),
                    obs_pitch=int(obs_pitch),
                    obs_conf=float(obs_conf),
                    params=params,
                )
                for st_pitch in states
            ]

            # 각 state별로 루프 t와 state값이 정해져있음 
            # 처음이라는 t0과 state값 29에서 이전 후보들과의 비교 문 시작
            for st_idx, st_pitch in enumerate(states):
                best_cost: float = inf
                best_pi: int = -1

                # 전체 이전 상태를 다 보면 O(T*S^2)라 느려짐.
                # MIDI 범위가 좁다면 S가 작아서 가능하지만,
                # 안전하게 "근방 탐색"을 기본으로 둠 (현업에서도 흔한 최적화).
                
                # 후보 범위를 조정함 
                # 최소 -> 0 or 현재인덱스 -12 
                # 최대 -> 최대인덱스-1 or 현재인덱스 +12
                cand_prev: Iterable[int] = self._prev_candidates(
                    cur_index=st_idx,
                    S=S,
                    radius=12, 
                )
                
                # 추정한 범위 내에서 pitch를 조사함
                # trans에는 옥타브 변경한 가중치결과값이 들어감
                for cand_pitch in cand_prev:
                    trans: float = self._transition_cost(
                        prev_pitch=int(states[cand_pitch]), # 이전에 걸러온 피치
                        cur_pitch=int(st_pitch), # 전체후보피치
                        params=params,
                    )
                    
                    # c에는 prev_cost[]
                    c: float = prev_cost[cand_pitch] + trans # 가장 적은비용
                    if c < best_cost:
                        best_cost = c # 가장 작은값이 저장됨
                        best_pi = cand_pitch # 최고의 인덱스
                
                # 현재 cost = emission_cost + transition_cost + prev_cost
                cur_cost[st_idx] = best_cost + emit_costs[st_idx]
                
                # 이전 index = [t][현재인덱스] = best_p
                prev_idx[t][st_idx] = best_pi

            # prev_cost와 cur_cost에는 각각 cur_cost를 저장하고 cur_cost는 다시 비움
            prev_cost, cur_cost = cur_cost, [inf] * S

        # backtrace
        last_state: int = int(min(range(S), key=lambda i: prev_cost[i]))
        path_state_idx: list[int] = [0] * T
        path_state_idx[T - 1] = last_state
        for t in range(T - 1, 0, -1):
            path_state_idx[t - 1] = prev_idx[t][path_state_idx[t]]

        # 적용: pitch만 바꾸고 나머지(t, conf)는 유지
        out: list[BasicPitchFramePitchDTO] = []
        for t in range(T):
            st_pitch: int = int(states[path_state_idx[t]])
            f: BasicPitchFramePitchDTO = frames[t]
            out.append(
                BasicPitchFramePitchDTO(
                    t=float(f.t),
                    pitch_midi=int(st_pitch),
                    confidence=None if f.confidence is None else float(f.confidence),
                )
            )
        return out
    
    def normalize_file(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        file_name: str = "frame_octave.json",
        params: FramePitchOctaveNormalizeParams,
        overwrite: bool = True,
        ) -> Path:
        if not input_path.exists():
            raise FileNotFoundError(f"input not found: {input_path}")

        # output_dir는 디렉토리로 취급
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path: Path = output_dir / file_name

        if output_path.exists() and not overwrite:
            raise FileExistsError(f"output already exists: {output_path}")

        with input_path.open("r", encoding="utf-8") as f:
            raw_obj: object = json.load(f)

        frames: list[BasicPitchFramePitchDTO] = self._parse_frames_json(raw_obj)

        out_frames: list[BasicPitchFramePitchDTO] = self.normalize(
            frames=frames,
            params=params,
        )

        payload: list[dict[str, Any]] = [
            {
            "   t": float(fr.t),
                "pitch_midi": int(fr.pitch_midi),
                "confidence": None if fr.confidence is None else float(fr.confidence),
            }
            for fr in out_frames
        ]

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return output_path




    # 이전 상태 후보 범위를 제한해서 반환함
    @staticmethod
    def _prev_candidates(*, cur_index: int, S: int, radius: int) -> Iterable[int]:
        lo: int = max(0, cur_index - int(radius))
        hi: int = min(S - 1, cur_index + int(radius))
        return range(lo, hi + 1)


    # x값을 lo와 hi사이로 강제함
    @staticmethod
    def _clamp_float(*, x: float, lo: float, hi: float) -> float:
        if x < lo:
            return lo
        if x > hi:
            return hi
        return x
    
    
    # 신뢰도와 emisiion_cost 기반으로 평가함
    # input -> 모든피치, 실제피치, 실제신뢰도
    # 각 state별로 emission_cost를 계산할 예정
    """ 
        ! 지금 프레임에서 관측값과 얼마나 맞는가
        ! 한줄요약
        ! state_pitch별로 가장 가까운 +-12같은거 한 것을 찾아 옥타브와 이동거리를 저장함 
        ! 이것과 confidence 보정치를 찾아서 계산해서 점수를 return 함
    """
    def _emission_cost(
        self,
        *,
        state_pitch: int, # 숨겨진 상태의 후보 pitch 1개
        obs_pitch: int, # basic_pitch에서 받아온 pitch 1개
        obs_conf: float | None, # basic_pitch에서 받아온 confidence 1개
        params: FramePitchOctaveNormalizeParams,
    ) -> float:
        """
        실제로 나온 pitch에 비해서
        예측 pitch가 obs_pitch에 +12 -12 같은거를 하고 어디에 가까운지 보고 비용을 줌 
        
        confidence에서  emission이 
        높을수록 더 날카롭게 -> conf신뢰
        낮을수록 더 평평하게 함 -> conf불신
        """
        
        conf_floor: float = float(params.conf_floor) # confidence 바닥
        conf_power: float = float(params.conf_power) # 루트
        conf_default : float = float(params.conf_default) # confidence 최소 가중치
        conf_cost : float = float(params.conf_cost) # confidence 보정치

        c: float = conf_floor if obs_conf is None else float(obs_conf)
        c = self._clamp_float(x=float(c), lo=conf_floor, hi=1.0)
        
        conf_w: float = float(c**conf_power) # confidence 가중치를 한 결과

        # 가장 가까웠던 alias가 몇 옥타브 이동이었는지
        best_octaves: int | None = None
        
        # 현재 state_pitch와 옥타브 +- 후보들 중에서 가장 작은 세미톤 거리를 찾기 위한 최소값 저장 변수
        best_absdiff: int = 10**9 
        
        # 이전 pitch에 +12 -12등을 함
        for k in params.alias_semitones:
            
            # 실제 pitch에 +-12등을 함
            cand: int = int(obs_pitch) + int(k)
            
            # 현재상태후보 - 관측보정후보를 실시하고 가장 가까운 거리를 저장함
            d: int = abs(int(state_pitch) - int(cand)) # 현재상태후보 - 관측보정후보
            if d < best_absdiff:
                best_absdiff = d
                best_octaves = abs(int(k)) // 12

        octs: int = 0 if best_octaves is None else int(best_octaves) # 최고로 가까운 옥타브 비용 저장
        alias_pen: float = float(octs) * float(params.alias_cost_per_octave) # 옥타브*옥타브가중치

        # conf_w가 높을수록(best_absdiff, alias_pen)에 민감하게
        # conf_w가 낮으면 emission이 완만해져서 transition(연속성)이 더 힘을 갖는다.
        
        # 둘의 거리 + 옥타브패널티
        return (float(best_absdiff) + alias_pen) * (conf_default + conf_cost * conf_w) 

    # 
    # ! 이전 프레임에서 얼마나 자연스러운가
    @staticmethod
    def _transition_cost(
        *,
        prev_pitch: int, # 이전 pitch 
        cur_pitch: int, # 현재 pitch
        params: FramePitchOctaveNormalizeParams,
    ) -> float:
        """
        연속성 비용:
        - 작은 이동은 허용
        - 큰 이동(특히 ±12의 배수 점프)은 추가 패널티
        """
        dp: int = abs(int(cur_pitch) - int(prev_pitch))  # 이전보다 얼마나 pich 가 움직였는가
        step_cost: float = float(params.lambda_step) * float(dp) # 한피치당의 비용가중치
        is_oct_like: bool = (dp % 12 == 0) # 만약 12배수라면
        oct_cost: float = float(params.lambda_oct) if is_oct_like else 0.0 # 한 옥타브당 12

        # 옥타브 움직이면 가중치 대빵 아니라면 pitch만큼 가중치 부여
        return step_cost + oct_cost
    
    def _parse_frames_json(self, obj: object) -> list[BasicPitchFramePitchDTO]:
        """
        input JSON 기대 형태(권장):
        [
          {"t": 0.00, "pitch_midi": 45, "confidence": 0.87},
          ...
        ]
        """
        if not isinstance(obj, list):
            raise ValueError("frames json must be a list of objects")

        out: list[BasicPitchFramePitchDTO] = []
        for i, row_obj in enumerate(obj):
            if not isinstance(row_obj, dict):
                raise ValueError(f"frames[{i}] must be an object")

            t_obj: object = row_obj.get("t")
            pitch_obj: object = row_obj.get("pitch_midi", row_obj.get("pitch"))  # 호환
            conf_obj: object = row_obj.get("confidence", row_obj.get("conf"))

            if t_obj is None or pitch_obj is None:
                raise ValueError(f"frames[{i}] missing required keys: t, pitch_midi")

            t: float = float(t_obj)
            pitch_midi: int = int(pitch_obj)
            confidence: float | None = None if conf_obj is None else float(conf_obj)

            out.append(
                BasicPitchFramePitchDTO(
                    t=t,
                    pitch_midi=pitch_midi,
                    confidence=confidence,
                )
            )
        return out