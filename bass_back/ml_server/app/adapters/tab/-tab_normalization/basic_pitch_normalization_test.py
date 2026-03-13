# tab_normalization_manual_test.py
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.adapters.tab.tab_normalization.basic_pitch_normalization_adapter import TabNormalizationAdapter
from app.application.ports.tab_normalization_port import TabNormalizationPort


def main() -> None:
    """
    실제 note_events.json 파일을 넣고
    정규화 결과가 정상 생성되는지 확인한다.
    """

    input_path: Path = Path(
        r"C:\bass_project\storage\test_11\basic_pitch\basic_pitch_json.json"
    )

    if not input_path.exists():
        raise FileNotFoundError(f"입력 파일 없음: {input_path}")

    output_dir: Path = Path(r"C:\bass_project\storage\test4")

    adapter: TabNormalizationAdapter = TabNormalizationAdapter()

    req: TabNormalizationPort = TabNormalizationPort(
        note_events_json_path=input_path,
        output_dir=output_dir,
    )

    # 🔥 async 함수 실행
    result = asyncio.run(adapter.normalize_and_save(req=req))

    out_path: Path = result.normalized_note_events_json_path

    # 1️⃣ 파일 생성 확인
    assert out_path.exists()
    print("✔ 파일 생성 성공:", out_path)

    # 2️⃣ JSON 형식 정상인지 확인
    raw: str = out_path.read_text(encoding="utf-8")
    payload = json.loads(raw)

    assert isinstance(payload, list)
    print("✔ JSON 형식 정상")

    # 3️⃣ 필수 키 확인
    for e in payload:
        assert "onset_sec" in e
        assert "offset_sec" in e
        assert "pitch_midi" in e
        assert e["offset_sec"] > e["onset_sec"]

    print("✔ 이벤트 구조 정상")

    # 4️⃣ 정렬 확인
    sorted_copy = sorted(
        payload,
        key=lambda x: (x["onset_sec"], x["offset_sec"], x["pitch_midi"]),
    )
    assert payload == sorted_copy

    print("✔ 정렬 정상")
    print("원본 개수:", len(json.loads(input_path.read_text(encoding="utf-8"))))
    print("정규화 후 개수:", len(payload))


if __name__ == "__main__":
    main()
