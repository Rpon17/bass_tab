from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from app.application.ports.bpm.bpm_port import BpmEstimatePort, BpmEstimateAdapterConfig
from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.domain.bpm_domain import BpmEstimationError


class LibrosaBpmEstimator(BpmEstimatePort):
    """
        onset_env생성(세기배열) -> original,high,middle,row 4가지로 나눠서 중앙값사용 -> *2 /2비교
        -> 범위 넘을 시 삭제

        입력 -> audio_path , 정규화된 onset_note
        출력 -> int값

    """

    def __init__(self, *, cfg: BpmEstimateAdapterConfig | None = None) -> None:
        self._cfg: BpmEstimateAdapterConfig = cfg or BpmEstimateAdapterConfig()

    async def estimate_bpm(
        self,
        *,
        input_wav_path: Path,
        note: list[BasicPitchNoteEventDTO],
        start_seconds: float = 0.0,
        duration_seconds: float | None = None,
        sr: int = 22050,
    ) -> int:
        if not input_wav_path.exists():
            raise FileNotFoundError(f"audio not found: {input_wav_path}")

        if start_seconds < 0.0:
            raise ValueError("start_seconds must be >= 0.0")
        if duration_seconds is not None and duration_seconds <= 0.0:
            raise ValueError("duration_seconds must be > 0.0 or None")
        if sr <= 0:
            raise ValueError("sr must be > 0")

        if not note:
            raise ValueError("note is required")

        try:
            return await asyncio.to_thread(
                self._estimate_sync,
                input_wav_path,
                float(start_seconds),
                None if duration_seconds is None else float(duration_seconds),
                int(sr),
                note,
            )
        except BpmEstimationError:
            raise
        except Exception as e:
            raise BpmEstimationError(f"bpm estimation failed: {e}") from e

    # normalize_file은 input_wav_path와 input_json_path를 받는식으로 해줘
    # 그리고 이건 print("bpm얼마") 이런식으로 출력만 하는식으로 해줘
    async def estimat_bpm_file(
        self,
        *,
        input_wav_path: Path,
        input_json_path: Path,
        start_seconds: float = 0.0,
        duration_seconds: float | None = None,
        sr: int = 22050,
    ) -> None:
        if not input_json_path.exists():
            raise FileNotFoundError(f"json not found: {input_json_path}")

        raw: Any
        with input_json_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, list):
            raise ValueError("input_json_path must contain a JSON list of note events")

        notes: list[BasicPitchNoteEventDTO] = []
        for row in raw:
            if not isinstance(row, dict):
                continue

            # common keys: start_time / end_time / pitch_midi / confidence
            st_any: Any = row.get("start_time", row.get("start", row.get("t")))
            et_any: Any = row.get("end_time", row.get("end"))
            pm_any: Any = row.get("pitch_midi", row.get("pitch"))

            if st_any is None or pm_any is None:
                continue

            start_time: float = float(st_any)
            end_time: float = float(et_any) if et_any is not None else float(start_time)
            pitch_midi: int = int(pm_any)

            conf_any: Any = row.get("confidence", None)
            confidence: float | None = None if conf_any is None else float(conf_any)

            notes.append(
                BasicPitchNoteEventDTO(
                    start_time=start_time,
                    end_time=end_time,
                    pitch_midi=pitch_midi,
                    confidence=confidence,
                )
            )

        bpm: int = await self.estimate_bpm(
            input_wav_path=input_wav_path,
            note=notes,
            start_seconds=float(start_seconds),
            duration_seconds=None if duration_seconds is None else float(duration_seconds),
            sr=int(sr),
        )

        print(f"bpm {bpm}")

    # 싱크추정
    def _estimate_sync(
        self,
        input_audio_path: Path,
        start_seconds: float,
        duration_seconds: float | None,
        sr: int,
        note: list[BasicPitchNoteEventDTO],
    ) -> int:
        import librosa  # type: ignore

        y: np.ndarray
        sr_loaded: int

        y, sr_loaded = librosa.load(
            path=str(input_audio_path),
            sr=sr,
            mono=True,
            offset=start_seconds,
            duration=duration_seconds,
        )

        if y.size < sr_loaded:
            raise BpmEstimationError("audio too short to estimate bpm")

        y_for_beat: np.ndarray = y

        y_harm: np.ndarray  # 지속음
        y_perc: np.ndarray  # 순간음
        y_harm, y_perc = librosa.effects.hpss(y_for_beat)
        y_for_beat = y_perc  # bpm추정은 순간음만 사용

        # onset_env -> 프레임별 타격된 세기들의 배열
        onset_env: np.ndarray = self._compute_onset_env(
            librosa=librosa,
            y=y_for_beat,
            sr_loaded=sr_loaded,
        )

        if onset_env.size < 8:
            raise BpmEstimationError("onset envelope too short")

        # beat_track을 이용해서 tempo -> bpm을 얻어냄
        tempo: float
        beat_frames: np.ndarray
        tempo, beat_frames = librosa.beat.beat_track(
            onset_envelope=onset_env,
            sr=sr_loaded,
            hop_length=self._cfg.hop_length,
            units="frames",
        )

        beat_times: np.ndarray = librosa.frames_to_time(
            beat_frames,
            sr=sr_loaded,
            hop_length=self._cfg.hop_length,
        )

        best_tempo: float = float(tempo)
        best_score: float = -1.0

        candidates: list[float] = [
            float(tempo),
            float(tempo) * 2.0,
            float(tempo) * 0.5,
        ]

        min_bpm: float = float(self._cfg.min_bpm)
        max_bpm: float = float(self._cfg.max_bpm)

        for cand in candidates:
            if not math.isfinite(cand) or cand <= 0.0:
                continue

            # 후보가 극단적으로 범위를 벗어나면 스킵(불필요 계산 방지)
            if cand < min_bpm * 0.5 or cand > max_bpm * 2.0:
                continue

            t_cand: float
            bf_cand: np.ndarray
            t_cand, bf_cand = librosa.beat.beat_track(
                onset_envelope=onset_env,
                sr=sr_loaded,
                hop_length=self._cfg.hop_length,
                units="frames",
                start_bpm=float(cand),  # cfg.start_bpm이 아니라 후보 평가를 위한 start_bpm
            )

            score: float = self._score_beats(onset_env=onset_env, beat_frames=bf_cand)
            if score > best_score:
                best_score = score
                best_tempo = float(t_cand)

        bpm_f: float = float(best_tempo)
        bpm_f = self._fold_bpm(bpm=bpm_f, min_bpm=self._cfg.min_bpm, max_bpm=self._cfg.max_bpm)

        bpm_round: int = self._to_int_bpm(bpm=bpm_f, mode=str(self._cfg.round_mode))

        # 후보 4개 준비: [bpm/2, bpm, bpm*2, bpm*4]
        bpm_list: list[float] = [float(bpm_round) / 2.0, float(bpm_round), float(bpm_round) * 2.0,float(bpm_round) * 4.0 ]
        bpm_list = [bl for bl in bpm_list if float(min_bpm) <= float(bl) <= float(max_bpm)]
        if not bpm_list:
            bpm_list = [float(bpm_round)]

        # 각 후보마다 beat_time 만들기 (가능하면 beat_track(..., start_bpm=cand, units="time")로 생성)
        best_bpm: float = float(bpm_list[0])
        best_bpm_score: float = -1.0

        for cand_bpm in bpm_list:
            tempo_c: float
            beat_time_c: np.ndarray
            tempo_c, beat_time_c = librosa.beat.beat_track(
                onset_envelope=onset_env,
                sr=sr_loaded,
                hop_length=self._cfg.hop_length,
                units="time",
                start_bpm=float(cand_bpm),
            )

            # bass onset start_time과 비교 점수 계산
            score_c: float = self._bpm_note_compare(
                beat_time=list(map(float, beat_time_c.tolist())),
                note=note,
                configs=self._cfg,
            )
            print(
                f"[BPM TEST] cand={float(cand_bpm):.2f} "
                f"tempo_out={float(tempo_c):.2f} "
                f"beats_n={int(beat_time_c.size)} "
                f"beat0={float(beat_time_c[0]) if int(beat_time_c.size) > 0 else -1.0:.3f} "
                f"beat_last={float(beat_time_c[-1]) if int(beat_time_c.size) > 0 else -1.0:.3f} "
                f"score={float(score_c):.4f}"
                )
            
            if score_c > best_bpm_score:
                best_bpm_score = float(score_c)
                best_bpm = float(cand_bpm)

        bpm: int = self._to_int_bpm(bpm=float(best_bpm), mode=str(self._cfg.round_mode))

        print(f"BPM추정 완료: {bpm}")
        return int(bpm)

    # onset_env -> 프레임별 얼마나 강한 타격이 발생했는가
    def _compute_onset_env(
        self,
        *,
        librosa: object,
        y: np.ndarray,
        sr_loaded: int,
    ) -> np.ndarray:
        # type: ignore[no-any-return]
        hop: int = int(self._cfg.hop_length)

        # 기본 onset
        onset_base: np.ndarray = librosa.onset.onset_strength(  # type: ignore[attr-defined]
            y=y,
            sr=sr_loaded,
            hop_length=hop,
        )

        # 주파수 대역별로 따로 계산함
        if not bool(self._cfg.use_multiband_onset):
            return onset_base

        bands: list[tuple[float, float]] = [
            (20.0, 180.0),  # low (kick/bass)
            (180.0, 2000.0),  # mid (snare/body)
            (2000.0, 8000.0),  # high (hat/attack)
        ]

        # envs에는 original,low,mid.high 4가지 배열이 들어감
        envs: list[np.ndarray] = [onset_base]
        for fmin, fmax in bands:
            env: np.ndarray = librosa.onset.onset_strength(  # type: ignore[attr-defined]
                y=y,
                sr=sr_loaded,
                hop_length=hop,
                fmin=float(fmin),
                fmax=float(fmax),
            )
            envs.append(env)

        # 4가지 배열의 길이를 맞춤
        min_len: int = min(int(e.size) for e in envs if e is not None)
        envs = [e[:min_len] for e in envs]

        agg: str = str(self._cfg.onset_aggregate).strip().lower()

        # 4개를 4X@ 로 합침
        stacked: np.ndarray = np.stack(envs, axis=0)

        # 최대값으로 할지 -> 이건 포트에서 정한디디
        if agg == "max":
            out: np.ndarray = np.max(stacked, axis=0)
        elif agg == "mean":
            out = np.mean(stacked, axis=0)
        else:
            out = np.median(stacked, axis=0)

        return out.astype(np.float32)

    # beats별로 score를 분배함
    # 벌점 + 베스트
    def _score_beats(self, *, onset_env: np.ndarray, beat_frames: np.ndarray) -> float:
        if beat_frames is None or int(beat_frames.size) == 0:
            return -1.0
        if onset_env is None or int(onset_env.size) == 0:
            return -1.0

        idx: np.ndarray = beat_frames.astype(np.int64, copy=False)
        idx = np.clip(idx, 0, int(onset_env.size) - 1)

        w: int = 2
        n_env: int = int(onset_env.size)

        def peak_at(i: int) -> float:
            lo: int = int(i - w)
            hi: int = int(i + w)
            if lo < 0:
                lo = 0
            if hi >= n_env:
                hi = n_env - 1
            return float(np.max(onset_env[lo : hi + 1]))

        # 1) beat 점수
        s_beat: float = 0.0
        for i in idx:
            s_beat += peak_at(int(i))
        n: int = int(idx.size)
        beat_mean: float = s_beat / float(n) if n > 0 else -1.0

        # 2) midpoint(= offbeat) 점수
        #    half가 틀리면 midpoint에 강한 onset이 많이 잡힘 -> 벌점
        if n < 2:
            return beat_mean

        mid_idx: list[int] = []
        for k in range(n - 1):
            m: int = int((int(idx[k]) + int(idx[k + 1])) // 2)
            if 0 <= m < n_env:
                mid_idx.append(m)

        if not mid_idx:
            return beat_mean

        s_mid: float = 0.0
        for m in mid_idx:
            s_mid += peak_at(int(m))
        mid_mean: float = s_mid / float(len(mid_idx))

        beta: float = 0.8  # 0.5~1.2 사이로 튜닝
        return float(beat_mean - beta * mid_mean)

    # bpm을 반올림해줌
    def _to_int_bpm(self, *, bpm: float, mode: str) -> int:
        m: str = mode.strip().lower()
        if m == "floor":
            return int(math.floor(float(bpm)))
        if m == "ceil":
            return int(math.ceil(float(bpm)))
        return int(round(float(bpm)))

    # bpm범위에 맞게 설정함 범위를 넘어간다면 *2 혹은 /2
    def _fold_bpm(self, *, bpm: float, min_bpm: float, max_bpm: float) -> float:
        if not math.isfinite(bpm) or bpm <= 0.0:
            return float(min_bpm)

        folded: float = float(bpm)
        while folded < float(min_bpm):
            folded *= 2.0
        while folded > float(max_bpm):
            folded *= 0.5

        if folded < float(min_bpm):
            folded = float(min_bpm)
        if folded > float(max_bpm):
            folded = float(max_bpm)
        return float(folded)

    def _bpm_note_compare(
        self,
        *,
        beat_time: list[float],
        note: list[BasicPitchNoteEventDTO],
        configs: BpmEstimateAdapterConfig,
    ) -> float:

        start_time_list: list[float] = [float(st.start_time) for st in note]
        start_time_list.sort()

        if not start_time_list or not beat_time:
            return -1.0

        beats: list[float] = sorted(float(b) for b in beat_time)

        cut_outline: int = round(len(start_time_list) / 500)

        # 1. 비트 리스트 테두리 자름
        if len(beats) > 2 * cut_outline:
            beats = beats[cut_outline:-cut_outline]

        if len(beats) < 3:
            return -1.0

        # 2. beat interval(중앙값) 계산
        intervals: list[float] = [beats[i + 1] - beats[i] for i in range(len(beats) - 1)]
        beat_interval: float = float(np.median(intervals))
        if not math.isfinite(beat_interval) or beat_interval <= 0.0:
            return -1.0

        # ------------------------------
        # (A) phase 최적화
        #   - onset들의 (t mod T) 분포에서 가장 많이 몰리는 phase를 offset으로 선택
        # ------------------------------
        phases: list[float] = [float(t % beat_interval) for t in start_time_list]
        if not phases:
            return -1.0

        # coarse histogram으로 대표 phase 선택 (코드량 최소)
        n_bins: int = 24
        bin_w: float = float(beat_interval) / float(n_bins)
        if bin_w <= 0.0:
            return -1.0

        counts: list[int] = [0] * n_bins
        for p in phases:
            bi: int = int(p // bin_w)
            if bi < 0:
                bi = 0
            if bi >= n_bins:
                bi = n_bins - 1
            counts[bi] += 1

        best_bin: int = int(max(range(n_bins), key=lambda i: counts[i]))
        offset: float = (float(best_bin) + 0.5) * float(bin_w)

        # beats를 offset만큼 이동 (phase 정렬)
        beats_shifted: list[float] = [float(b + offset) for b in beats]

        # ------------------------------
        # (B) 정규화 거리 점수
        #   - dist_norm = dist / beat_interval (초 단위 편향 제거)
        #   - score = 1 - mean(dist_norm) (작을수록 좋음 → 점수는 클수록 좋게 변환)
        # ------------------------------
        import bisect

        dist_sum_norm: float = 0.0
        total: int = 0

        for t in start_time_list:
            idx: int = bisect.bisect_left(beats_shifted, t)

            dist: float = float("inf")
            if idx < len(beats_shifted):
                dist = min(dist, abs(beats_shifted[idx] - t))
            if idx > 0:
                dist = min(dist, abs(beats_shifted[idx - 1] - t))

            # 비정상 케이스 방어
            if not math.isfinite(dist):
                continue

            dist_sum_norm += float(dist) / float(beat_interval)
            total += 1

        if total == 0:
            return -1.0

        mean_dist_norm: float = float(dist_sum_norm) / float(total)

        # mean_dist_norm이 작을수록 좋음 → 점수는 클수록 좋게
        score: float = 1.0 - mean_dist_norm
        return float(score)