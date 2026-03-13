from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class NoteEvent:
    onset_sec: float
    offset_sec: float
    pitch_midi: int
    confidence: float | None
    

@dataclass(frozen=True)
class FretPos:
    string_no: int 
    fret_no: int

 
@dataclass(frozen=True)
class PlacedNote:
    bar_index: int
    step_index: int 
    pitch_midi: int
    pos: FretPos