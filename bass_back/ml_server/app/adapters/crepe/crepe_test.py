from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from app.adapters.crepe.crepe_adapter import CrepeAdapter
from app.application.ports.crepe_port import CrepeParams
from app.application.ports.crepe_port import CrepeParams

print("CrepeParams file:", inspect.getfile(CrepeParams))
print("CrepeParams fields:", getattr(CrepeParams, "__dataclass_fields__", {}).keys())
print("CrepeParams annotations:", getattr(CrepeParams, "__annotations__", {}))
print(inspect.getsource(CrepeParams))



async def main() -> None:
    adapter: CrepeAdapter = CrepeAdapter()

    params: CrepeParams = CrepeParams(
        input_wav_path=Path(r"C:\bass_project\storage\demucs_test_output\asset\test_1\audio\bass_only.wav"),
        output_dir=Path(r"C:\bass_project\storage\crepe_test_output"),
        asset_id="test_1",
        model_capacity="tiny",
        step_size_ms=10,
        use_viterbi=True,
        conf_threshold=0.40,
        return_unvoiced_as_none=True,
        debug_save_csv=True,
        debug_save_npz=False,
    )

    out_path: Path = await adapter.export_frame_pitch(params=params)
    print("✅ crepe exported:", out_path)


if __name__ == "__main__":
    asyncio.run(main())