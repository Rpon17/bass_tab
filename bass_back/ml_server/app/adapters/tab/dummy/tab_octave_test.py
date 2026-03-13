from pathlib import Path

from bass_back.ml_server.app.adapters.tab.frame.frame_octave_adapter import (
    ViterbiFramePitchOctaveNormalizeAdapter,
    FramePitchOctaveNormalizeParams,
)


def main() -> None:
    # ✅ 40 미만 무조건 +12 정책 포함된 어댑터
    adapter = ViterbiFramePitchOctaveNormalizeAdapter(
        alpha_tab_min_midi=40
    )

    params = FramePitchOctaveNormalizeParams(
        midi_min=40,          # ✅ AlphaTab 시작을 40으로 고정
        midi_max=70,

        # --- alias 후보 ---
        alias_semitones=[0, -12, 12],

        # --- emission 관련 ---
        alias_cost_per_octave=1.0,
        conf_floor=0.2,
        conf_power=2.0,
        conf_default=1.0,
        conf_cost=1.0,

        # --- transition 관련 ---
        lambda_step=0.15,
        lambda_oct=3.0,
    )

    input_path: Path = Path(
        r"C:\bass_project\storage\basic_pitch\test1\assets\test_asset_001\frame_pitches.json"
    )

    output_dir: Path = Path(
        r"C:\bass_project\storage\frame_octave"
    )

    out_path: Path = adapter.normalize_file(
        input_path=input_path,
        output_dir=output_dir,
        file_name="frame_pitch_octave_normalized.json",
        params=params,
        overwrite=True,
    )

    print(f"[OK] saved to: {out_path}")


if __name__ == "__main__":
    main()