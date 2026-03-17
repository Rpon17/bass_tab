from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from app.adapters.bpm.bpm_estimate_adapter import (
    LibrosaBpmEstimator,
    BpmEstimateAdapterConfig,
)


@dataclass(frozen=True)
class TrialResult:
    idx: int
    true_bpm: int
    est_bpm: int
    ok: bool
    note: str
    wav_path: Path


def make_click_track(
    *,
    bpm: float,
    seconds: float,
    sr: int,
    click_ms: float = 8.0,
    amp: float = 0.9,
) -> np.ndarray:
    n: int = int(round(seconds * sr))
    y: np.ndarray = np.zeros(n, dtype=np.float32)

    interval: int = int(round((60.0 / float(bpm)) * sr))
    click_len: int = max(1, int(round((click_ms / 1000.0) * sr)))

    decay: np.ndarray = np.exp(-np.linspace(0.0, 6.0, click_len)).astype(np.float32)

    for i in range(0, n, interval):
        j: int = i + click_len
        if j <= n:
            y[i:j] += float(amp) * decay

    m: float = float(np.max(np.abs(y)) + 1e-9)
    if m > 1.0:
        y = (y / m).astype(np.float32)
    return y


def is_match(
    *,
    true_bpm: int,
    est_bpm: int,
    tol_bpm: float,
    allow_half_double: bool,
) -> tuple[bool, str]:
    t: float = float(true_bpm)
    e: float = float(est_bpm)

    diff: float = abs(e - t)
    if diff <= tol_bpm:
        return True, f"direct (±{tol_bpm})"

    if not allow_half_double:
        return False, f"diff={diff:.2f}"

    diff_half: float = abs(e - (t * 0.5))
    if diff_half <= tol_bpm:
        return True, f"half (est≈true/2 ±{tol_bpm})"

    diff_double: float = abs(e - (t * 2.0))
    if diff_double <= tol_bpm:
        return True, f"double (est≈true*2 ±{tol_bpm})"

    return False, f"diff={diff:.2f} (half={diff_half:.2f}, double={diff_double:.2f})"


async def run_trials() -> None:
    out_dir: Path = Path(r"C:\bass_project\storage\bpm_synth_trials")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 설정
    n_trials: int = 10
    sr: int = 22050
    seconds: float = 12.0
    tol_bpm: float = 1.0
    allow_half_double: bool = True

    # 랜덤 BPM 샘플링 (원하면 고정 리스트로 바꿔도 됨)
    rng: random.Random = random.Random(2026)
    bpms: list[int] = [int(rng.randint(50, 200)) for _ in range(n_trials)]

    estimator: LibrosaBpmEstimator = LibrosaBpmEstimator(
        cfg=BpmEstimateAdapterConfig(
            start_bpm=120.0,
            hop_length=512,
            min_bpm=40.0,
            max_bpm=220.0,
            # round_mode="round",  # 네 config에 있으면 켜도 됨
        )
    )

    results: list[TrialResult] = []
    for i, true_bpm in enumerate(bpms, start=1):
        wav_path: Path = out_dir / f"click_{i:02d}_{int(true_bpm)}bpm.wav"
        y: np.ndarray = make_click_track(bpm=float(true_bpm), seconds=seconds, sr=sr)
        sf.write(str(wav_path), y, sr)

        est_bpm: int = int(await estimator.estimate_bpm(input_audio_path=wav_path, sr=sr))

        ok, note = is_match(
            true_bpm=int(true_bpm),
            est_bpm=int(est_bpm),
            tol_bpm=tol_bpm,
            allow_half_double=allow_half_double,
        )

        results.append(
            TrialResult(
                idx=int(i),
                true_bpm=int(true_bpm),
                est_bpm=int(est_bpm),
                ok=bool(ok),
                note=str(note),
                wav_path=wav_path,
            )
        )

    # 리포트
    hit: int = sum(1 for r in results if r.ok)
    print(
        f"Trials: {n_trials}, Hits: {hit}/{n_trials}  "
        f"(tol_bpm={tol_bpm}, allow_half_double={allow_half_double})"
    )
    print("-" * 90)
    for r in results:
        status: str = "OK" if r.ok else "MISS"
        print(
            f"[{r.idx:02d}] true={r.true_bpm:4d}  est={r.est_bpm:4d}  "
            f"{status:4s}  {r.note:28s}  {r.wav_path.name}"
        )


if __name__ == "__main__":
    asyncio.run(run_trials())