from typing import Literal, TypedDict, Any, Optional

FunctionMode = Literal["separate", "analyze", "tab", "full"]
TabMode = Literal["original", "root"]

class MlProcessResult(TypedDict, total=False):
    bass_wav_path: str
    notes: list[dict[str, Any]]
    bpm: float
    tabs: list[dict[str, Any]]
    meta: dict[str, Any]

class MlProcessResponse(TypedDict):
    ok: bool
    function_mode: FunctionMode
    tab_mode: TabMode  # ✅ 항상 포함(필수)
    result: Optional[MlProcessResult]
    error: Optional[str]
