from __future__ import annotations

from pathlib import Path

from app.application.ports.basic_pitch.basic_pitch_port import BasicPitchNoteEventDTO
from app.application.ports.tab.merge.original.onset_frame_plus_port import OnsetFrameFuseParams
from app.application.ports.tab.merge.root.root_note_port import RootTabBuildPort
from app.application.ports.tab.tab.original_tab.original_tab_port import OriginalTabGeneratePort
from app.application.ports.tab.tab.original_tab.viterbi_port import (
    BassTabViterbiStepDTO,
)


class FakeRootTabBuildPort(RootTabBuildPort):
    def build(
        self,
        *,
        bpm: float,
        original_notes: list[BasicPitchNoteEventDTO],
        params: OnsetFrameFuseParams,
    ) -> list[BasicPitchNoteEventDTO]:
        print("[OK] RootTabBuildPort.build signature matched")
        print(f"  bpm={bpm}")
        print(f"  notes={len(original_notes)}")
        print(f"  params={params}")
        return original_notes

    def build_file(
        self,
        *,
        bpm: float,
        original_notes: list[BasicPitchNoteEventDTO],
        output_dir: str,
        params: OnsetFrameFuseParams,
    ) -> None:
        print("[OK] RootTabBuildPort.build_file signature matched")
        print(f"  output_dir type={type(output_dir).__name__}")
        print(f"  output_dir={output_dir}")


class FakeOriginalTabGeneratePort(OriginalTabGeneratePort):
    def tab_generate(
        self,
        *,
        original_json: list[BasicPitchNoteEventDTO],
        bpm: int,
        output_dir: Path,
        asset_id: str,
    ) -> Path:
        print("[OK] OriginalTabGeneratePort.tab_generate signature matched")
        print(f"  original_json count={len(original_json)}")
        print(f"  bpm={bpm}")
        print(f"  output_dir type={type(output_dir).__name__}")
        print(f"  asset_id={asset_id}")

        out_path: Path = output_dir / "tab" / "original_tab.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("[]", encoding="utf-8")
        return out_path


def main() -> None:
    root_port: RootTabBuildPort = FakeRootTabBuildPort()
    original_port: OriginalTabGeneratePort = FakeOriginalTabGeneratePort()

    bpm: int = 120
    asset_root_path: Path = Path(r"C:\bass_project\storage\usecase_test")
    asset_id: str = "asset_test_001"

    original_notes: list[BasicPitchNoteEventDTO] = [
        BasicPitchNoteEventDTO(
            start_time=0.0,
            end_time=0.5,
            pitch_midi=40,
            confidence=0.9,
        ),
        BasicPitchNoteEventDTO(
            start_time=0.5,
            end_time=1.0,
            pitch_midi=43,
            confidence=0.8,
        ),
    ]

    viterbi_steps: list[BassTabViterbiStepDTO] = [
        BassTabViterbiStepDTO(
            note_index=0,
            pitch_midi=40,
            start_time=0.0,
            end_time=0.5,
            line=1,
            fret=0,
        ),
        BassTabViterbiStepDTO(
            note_index=1,
            pitch_midi=43,
            start_time=0.5,
            end_time=1.0,
            line=2,
            fret=0,
        ),
    ]

    # 1) RootTabBuildPort.params 타입 확인
    root_notes: list[BasicPitchNoteEventDTO] = root_port.build(
        bpm=float(bpm),
        original_notes=original_notes,
        params=OnsetFrameFuseParams(),
    )
    print(f"[CHECK] root_notes count={len(root_notes)}")

    # 2) build_file() output_dir 타입 확인
    root_port.build_file(
        bpm=float(bpm),
        original_notes=original_notes,
        output_dir=str(asset_root_path),
        params=OnsetFrameFuseParams(),
    )

    # 3) tab_generate()가 viterbi_steps 없이 호출 가능한지 확인
    out_path: Path = original_port.tab_generate(
        original_json=original_notes,
        bpm=int(bpm),
        output_dir=asset_root_path,
        asset_id=asset_id,
    )
    print(f"[CHECK] original_tab path={out_path}")
    print(f"[CHECK] original_tab exists={out_path.exists()}")

    # 참고: 현재 포트 구조에서는 viterbi_steps를 넘길 곳이 없다.
    print(f"[INFO] viterbi_steps generated but unused count={len(viterbi_steps)}")


if __name__ == "__main__":
    main()