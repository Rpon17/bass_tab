from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F
import torchcrepe

from app.application.ports.crepe_port import CrepeParams, CrepePort


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(*, path: Path, payload: Any) -> None:
    _ensure_dir(path.parent)
    tmp_path: Path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _to_mono(wav: np.ndarray) -> np.ndarray:
    if wav.ndim == 1:
        return wav
    if wav.ndim == 2:
        return np.mean(wav, axis=1)
    raise ValueError(f"Unsupported wav ndim: {wav.ndim}")


def _normalize_audio(*, wav: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
    w: np.ndarray = wav.astype(np.float32, copy=False)
    if w.size <= 0:
        return w
    peak: float = float(np.max(np.abs(w)))
    if peak <= 0.0:
        return w
    scale: float = float(target_peak) / peak
    w = w * scale
    return np.clip(w, -1.0, 1.0)


def _freq_to_midi(freq_hz: float) -> int:
    if freq_hz <= 0.0:
        return 0
    return int(round(69.0 + 12.0 * math.log2(freq_hz / 440.0)))


def _map_model_capacity(capacity: str) -> str:
    m: str = str(capacity).lower().strip()
    if m in ("tiny", "full"):
        return m
    if m in ("small", "medium"):
        return "tiny"
    if m in ("large",):
        return "full"
    return "tiny"


def _sanitize_confidence(conf: float | None) -> float | None:
    if conf is None:
        return None
    if not math.isfinite(conf):
        return None
    # periodicity가 0~1이 아니면 신뢰도 해석 불가 -> None
    if conf < 0.0 or conf > 1.0:
        return None
    return conf


def _resample_1d_torch(*, wav: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return wav
    if wav.size <= 0:
        return wav

    t_in: int = int(wav.shape[0])
    t_out: int = int(round(float(t_in) * float(sr_out) / float(sr_in)))
    t_out = max(1, t_out)

    x: torch.Tensor = torch.from_numpy(wav.astype(np.float32, copy=False)).view(1, 1, t_in)
    y: torch.Tensor = F.interpolate(x, size=t_out, mode="linear", align_corners=False)
    out: np.ndarray = y.view(t_out).detach().cpu().numpy().astype(np.float32, copy=False)
    return out


def _torchcrepe_predict_safe(
    *,
    wav_t: torch.Tensor,
    sr: int,
    hop_length: int,
    fmin: float,
    fmax: float,
    model_name: str,
    batch_size: int,
    device: str,
) -> tuple[torch.Tensor, torch.Tensor | None]:
    try:
        out1: object = torchcrepe.predict(
            wav_t,
            sr,
            hop_length=hop_length,
            fmin=fmin,
            fmax=fmax,
            model=model_name,
            batch_size=batch_size,
            device=device,
            return_periodicity=True,
        )
        if isinstance(out1, tuple) and len(out1) == 2:
            return cast(torch.Tensor, out1[0]), cast(torch.Tensor, out1[1])
        if torch.is_tensor(out1):
            return cast(torch.Tensor, out1), None
    except TypeError:
        pass

    try:
        out2: object = torchcrepe.predict(
            wav_t,
            sr,
            hop_length=hop_length,
            fmin=fmin,
            fmax=fmax,
            model=model_name,
            batch_size=batch_size,
            return_periodicity=True,
        )
        if isinstance(out2, tuple) and len(out2) == 2:
            return cast(torch.Tensor, out2[0]), cast(torch.Tensor, out2[1])
        if torch.is_tensor(out2):
            return cast(torch.Tensor, out2), None
    except TypeError:
        pass

    out3: object = torchcrepe.predict(
        wav_t,
        sr,
        hop_length=hop_length,
        fmin=fmin,
        fmax=fmax,
        model=model_name,
        batch_size=batch_size,
    )
    if isinstance(out3, tuple) and len(out3) == 2:
        return cast(torch.Tensor, out3[0]), cast(torch.Tensor, out3[1])
    if torch.is_tensor(out3):
        return cast(torch.Tensor, out3), None

    raise RuntimeError(f"Unexpected torchcrepe.predict return type: {type(out3)}")


@dataclass(frozen=True)
class CrepeAdapter(CrepePort):
    async def export_frame_pitch(self, *, params: CrepeParams) -> Path:
        input_wav_path: Path = params.input_wav_path
        output_dir: Path = params.output_dir
        asset_id: str = params.asset_id

        if not input_wav_path.exists():
            raise FileNotFoundError(f"input wav not found: {input_wav_path}")

        out_dir: Path = output_dir / "assets" / asset_id / params.output_subdir
        _ensure_dir(out_dir)

        out_json_path: Path = out_dir / params.output_filename
        out_csv_path: Path = out_dir / (Path(params.output_filename).stem + ".csv")

        wav, sr = sf.read(str(input_wav_path), dtype="float32")
        wav_np: np.ndarray = np.asarray(wav, dtype=np.float32)

        if params.mono:
            wav_np = _to_mono(wav_np)

        sr_in: int = int(sr)
        sr_target: int = int(params.target_sr)
        if sr_target > 0 and sr_in != sr_target:
            wav_np = _resample_1d_torch(wav=wav_np, sr_in=sr_in, sr_out=sr_target)
            sr_in = sr_target

        wav_np = _normalize_audio(wav=wav_np, target_peak=0.95)

        wav_t: torch.Tensor = torch.tensor(wav_np, dtype=torch.float32).unsqueeze(0)
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
        wav_t = wav_t.to(device)

        hop_length: int = int(round(float(sr_in) * float(params.step_size_ms) / 1000.0))
        hop_length = max(1, int(hop_length))

        model_name: str = _map_model_capacity(str(params.model_capacity))

        # 베이스-only 안전 범위: 낮게 열어두고(20) 후단에서 옥타브 보정
        fmin: float = 20.0
        fmax: float = 400.0

        f0_t, periodicity_t = _torchcrepe_predict_safe(
            wav_t=wav_t,
            sr=int(sr_in),
            hop_length=hop_length,
            fmin=fmin,
            fmax=fmax,
            model_name=model_name,
            batch_size=1024,
            device=device,
        )

        f_arr: np.ndarray = f0_t.squeeze(0).detach().cpu().numpy()
        c_arr: np.ndarray | None = None
        if periodicity_t is not None:
            c_arr = periodicity_t.squeeze(0).detach().cpu().numpy()

        step_sec: float = float(params.step_size_ms) / 1000.0
        t_arr: np.ndarray = np.arange(int(f_arr.shape[0]), dtype=np.float64) * step_sec

        T: int = int(min(t_arr.shape[0], f_arr.shape[0], c_arr.shape[0] if c_arr is not None else f_arr.shape[0]))

        payload: list[dict[str, Any]] = []
        for i in range(T):
            t: float = float(t_arr[i])
            f0: float = float(f_arr[i])

            c0_raw: float | None = None if c_arr is None else float(c_arr[i])
            c0: float | None = _sanitize_confidence(c0_raw)

            # ✅ 단순 규칙: f0>0이면 무조건 midi 생성 (여기서 null 만들지 않음)
            if f0 <= 0.0:
                if params.return_unvoiced_as_none:
                    payload.append({"t": t, "pitch_midi": None, "confidence": c0, "freq_hz": f0})
                else:
                    payload.append({"t": t, "pitch_midi": 0, "confidence": c0, "freq_hz": f0})
                continue

            payload.append(
                {
                    "t": t,
                    "pitch_midi": int(_freq_to_midi(f0)),
                    "confidence": c0,
                    "freq_hz": f0,
                }
            )

        # 🔎 이 두 줄로 “저장 전” 상태 확정 가능 (필요하면 잠깐 켜고 확인)
        # print("payload len:", len(payload))
        # print("payload head:", payload[:5])

        _write_json(path=out_json_path, payload=payload)

        if params.debug_save_csv:
            with out_csv_path.open("w", encoding="utf-8", newline="") as f:
                w: csv.writer = csv.writer(f)
                w.writerow(["t", "freq_hz", "pitch_midi", "confidence"])
                for row in payload:
                    pitch_obj: object = row.get("pitch_midi", None)
                    conf_obj: object = row.get("confidence", None)
                    w.writerow(
                        [
                            float(row["t"]),
                            float(row.get("freq_hz", 0.0)),
                            "" if pitch_obj is None else int(cast(int, pitch_obj)),
                            "" if conf_obj is None else float(cast(float, conf_obj)),
                        ]
                    )

        return out_json_path