import asyncio
from pathlib import Path

from app.adapters.bpm.bpm_estimate_adapter import LibrosaBpmEstimator


async def main() -> None:
    # 🔹 테스트할 오디오 파일 경로
    audio_path: Path = Path(
        r"C:\bass_project\storage\songs\c422012dd22046ab95f91e537d59be1a\results\90b97c8940ef4dc1af030140ebb1b691\audio\original.mp3"
    )

    # 🔹 테스트할 onset note json 경로 (정규화된 onset_note json)
    note_json_path: Path = Path(
        r"C:\bass_project\storage\final\assets\test_asset_001\onset_note_normalization.json"
    )

    if not audio_path.exists():
        print(f"파일이 존재하지 않습니다: {audio_path.resolve()}")
        return

    if not note_json_path.exists():
        print(f"파일이 존재하지 않습니다: {note_json_path.resolve()}")
        return

    estimator: LibrosaBpmEstimator = LibrosaBpmEstimator()

    print("BPM 추정 시작...")

    # normalize_file은 print만 하고 None 반환
    await estimator.estimat_bpm_file(
        input_wav_path=audio_path,
        input_json_path=note_json_path,
    )


if __name__ == "__main__":
    asyncio.run(main())