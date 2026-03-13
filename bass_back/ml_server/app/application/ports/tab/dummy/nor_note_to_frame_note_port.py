from dataclasses import dataclass

@dataclass(frozen=True)
class NoteEvent:
    onset_sec: float
    offset_sec: float
    pitch_midi: int
    confidence: float


@dataclass(frozen=True)
class FrameLabels:
    frame_hz: float
    hop_sec: float
    midi_min: int
    midi_max: int
    num_frames: int
    pitches: list[int]   # 0 = rest
    confs: list[float]   # 0.0 = rest