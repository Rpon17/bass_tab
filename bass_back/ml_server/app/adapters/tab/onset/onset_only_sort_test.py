from __future__ import annotations

from pathlib import Path

from app.adapters.tab.onset.onset_only_sort_adapter import OnsetOnlySortAdapter


def main() -> None:
    input_json_path: Path = Path(
        r"C:\bass_project\storage\final\assets\test_asset_001\onset_note_normalization.json"
    )
    output_dir: Path = Path(r"C:\bass_project\storage\final\assets\test_asset_001")

    adapter: OnsetOnlySortAdapter = OnsetOnlySortAdapter()
    out_path: Path = adapter.normalize_file(
        input_json_path=input_json_path,
        output_dir=output_dir,
        overwrite=True,
    )

    print(f"[OK] saved to: {out_path}")


if __name__ == "__main__":
    main()