from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.application.ports.nor_note_to_frame_note_port import NoteEvent,FrameLabels

# 시간을 해당 시간 이전 프레임으로 매핑 onset
def _sec_to_frame_floor(*, t_sec: float, hop_sec: float) -> int:
    if t_sec <= 0.0:
        return 0
    return int(math.floor(t_sec / hop_sec))

# 시간을 해당 시간 이후 프레임으로 매핑 offset
def _sec_to_frame_ceil(*, t_sec: float, hop_sec: float) -> int:
    if t_sec <= 0.0:
        return 0
    return int(math.ceil(t_sec / hop_sec))

# 노트이벤트를 프레임라벨로 변경
def note_events_to_frame_labels(
    *,
    note_events: list[NoteEvent],
    frame_hz: float = 100.0,     # 초당 프레임이 몇개
    midi_min: int = 28,          # 최소 피치
    midi_max: int = 80,          # 최대 피치
    num_frames: int | None = None, # 프레임 개수
) -> FrameLabels:
    
    # 초당 프레임 오류제거
    if frame_hz <= 0.0:
        raise ValueError("frame_hz must be > 0.0")

    # hop -> 1프레임이 몇초인가
    hop_sec: float = 1.0 / frame_hz

    # num_frames를 지정하지 않으면 마지막 offset 기준으로 잡음 프레임 개수를 가져옴
    if num_frames is None:
        # 가장 늦게 끝나는 음
        max_offset_sec: float = 0.0
        for e in note_events:
            if e.offset_sec > max_offset_sec:
                max_offset_sec = e.offset_sec
        num_frames = _sec_to_frame_ceil(t_sec=max_offset_sec, hop_sec=hop_sec) + 1

    # pitch,confidence 배열
    pitches: list[int] = [0 for _ in range(num_frames)]
    confs: list[float] = [0.0 for _ in range(num_frames)]

    for e in note_events:
        pitch_midi: int = int(e.pitch_midi)
        conf: float = float(e.confidence)
        
        # 음역대 밖은 모두 버림
        if pitch_midi < midi_min or pitch_midi > midi_max:
            continue
        
        # 이 pitch가 있는 frame의 범위를 만듬
        onset_i: int = _sec_to_frame_floor(t_sec=float(e.onset_sec), hop_sec=hop_sec)
        offset_i: int = _sec_to_frame_ceil(t_sec=float(e.offset_sec), hop_sec=hop_sec)

        # 안전 클램프
        if onset_i < 0:
            onset_i = 0
        if offset_i > num_frames:
            offset_i = num_frames

        # 이 범위의 프레임동안의 pitch와 confs를 저장함
        for i in range(onset_i, offset_i):
            if conf > confs[i]:
                pitches[i] = pitch_midi
                confs[i] = conf

    # 이 정보들을 return 함
    return FrameLabels(
        frame_hz=frame_hz,
        hop_sec=hop_sec,
        midi_min=midi_min,
        midi_max=midi_max,
        num_frames=num_frames,
        pitches=pitches,
        confs=confs,
    )


def save_frame_labels_json(*, out_path: Path, labels: FrameLabels) -> None:
    payload: dict[str, Any] = {
        "frame_hz": labels.frame_hz,
        "hop_sec": labels.hop_sec,
        "midi_min": labels.midi_min,
        "midi_max": labels.midi_max,
        "num_frames": labels.num_frames,
        "pitches": labels.pitches,
        "confs": labels.confs,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")