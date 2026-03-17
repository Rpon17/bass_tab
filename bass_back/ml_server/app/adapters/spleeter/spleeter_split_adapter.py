from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from app.domain.models_domain import MLJob

""" 
    이 코드는 adapter인데
    
    input_wav_path, output_dir,볼륨(선택,기본10) 이 정보만 있으면 알아서 저장까지 해버림
    이제 main_server에 보낼것은 그냥 작업 뿐
    
    output_dir -> /storage/songs/{song_id}/results/{result_id}
    output_dir -> main_server에서 받은 result_path

    output_dir/audio : 최종 산출물 저장(유지)
    output_dir/stem  : 임시 산출물 저장(작업 후 삭제)

    input_wav_path -> /storage/songs/{song_id}/results/{result_id}/audio/original.wav
    
    여기서 저장한 original을 복사해서 저장하자
    output_dir -> /storage/songs/{song_id}/results/{result_id}/assets/{asset_id}/audio
    에 복사하자
"""


class SpleeterAdapter:
    async def split(
        self,
        *,
        input_wav_path: Path,
        output_dir: Path,
        asset_id: str,
        boosted_volume_db: float = 10.0,
    ) -> None:
        if not input_wav_path.exists():
            raise FileNotFoundError(f"input wav not found: {input_wav_path}")

        if boosted_volume_db < -24.0 or boosted_volume_db > 24.0:
            raise ValueError("boosted_volume_db must be between -24.0 and 24.0")

        output_dir = output_dir / "asset" / asset_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # /storage/songs/{song_id}/results/{result_id}/asset/asset_id/audio
        audio_dir: Path = output_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        # /storage/songs/{song_id}/results/{result_id}/asset/asset_id/stem
        stem_dir_root: Path = output_dir / "stem"
        stem_dir_root.mkdir(parents=True, exist_ok=True)

        try:
            # 여기서 저장한 original을 복사해서 저장하자
            original_copy: Path = audio_dir / "original.wav"
            shutil.copyfile(str(input_wav_path), str(original_copy))
            original_path: Path = original_copy

            # /storage/songs/{song_id}/results/{result_id}/asset/asset_id/stem/_spleeter_tmp
            spleeter_out_dir: Path = stem_dir_root / "_spleeter_tmp"
            spleeter_out_dir.mkdir(parents=True, exist_ok=True)

            # "spleeter seperate -p spleeter:4stems -o"
            # 즉 4가지 악기로 나누는 spleeter 해라
            cmd: list[str] = [
                "spleeter",
                "separate",
                "-p",
                "spleeter:4stems",
                "-o",
                str(spleeter_out_dir),
                str(original_path),
            ]

            # os에게 실행요청 (무거웅께..)
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # 에러나 결과 받아오기
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                raise RuntimeError(
                    f"Spleeter failed\nstdout={stdout.decode(errors='ignore')}\n"
                    f"stderr={stderr.decode(errors='ignore')}"
                )

            # 원래 spleeter 저장구조가 output_path/ input_path에서 확장자 뺀폴더 만듬/ 여기에 생성
            spleeter_job_dir: Path = spleeter_out_dir / original_path.stem
            if not spleeter_job_dir.exists():
                raise RuntimeError(f"Spleeter output directory not found: {spleeter_job_dir}")

            # 4stems 결과: vocals/drums/bass/other
            vocals_src: Path = spleeter_job_dir / "vocals.wav"
            drums_src: Path = spleeter_job_dir / "drums.wav"
            bass_src: Path = spleeter_job_dir / "bass.wav"
            other_src: Path = spleeter_job_dir / "other.wav"

            missing: list[str] = [
                name
                for name, p in [
                    ("vocals.wav", vocals_src),
                    ("drums.wav", drums_src),
                    ("bass.wav", bass_src),
                    ("other.wav", other_src),
                ]
                if not p.exists()
            ]
            if missing:
                raise RuntimeError(f"Spleeter stem files missing: {', '.join(missing)}")

            bass_removed: Path = audio_dir / "bass_removed.wav"
            bass_only: Path = audio_dir / "bass_only.wav"
            bass_boosted: Path = audio_dir / "bass_boosted.wav"

            # 1) bass_only 옮기기
            shutil.move(str(bass_src), str(bass_only))

            # 2) bass_removed 만들고 옮기기 3개 노래만 섞음
            await self._mix_many(
                input_paths=[vocals_src, drums_src, other_src],
                output_path=bass_removed,
            )

            # 3) bass_boosted 만들고 옮기기 4개섞는데 bass_boosted만 크게함
            await self._mix_boost(
                input_path_first=bass_removed,
                input_path_second=bass_only,
                output_path=bass_boosted,
                gain_db=boosted_volume_db,
            )

        finally:
            # stem 임시 폴더 삭제
            shutil.rmtree(stem_dir_root, ignore_errors=True)

    async def _mix_many(
        self,
        *,
        input_paths: list[Path],
        output_path: Path,
    ) -> None:
        if len(input_paths) < 2:
            raise ValueError("input_paths must have at least 2 paths")
        
        cmd: list[str] = ["ffmpeg", "-y"]
        for p in input_paths:
            cmd += ["-i", str(p)]

        cmd += [
            "-filter_complex",
            f"amix=inputs={len(input_paths)}:normalize=0[outa]",
            "-map",
            "[outa]",
            str(output_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg mix_many failed: {stderr.decode(errors='ignore')}")

    async def _mix_boost(
        self,
        *,
        input_path_first: Path,
        input_path_second: Path,
        output_path: Path,
        gain_db: float,
    ) -> None:
        # input 0: (vocals+drums+other)
        # input 1: bass_only (이것만 gain_db 만큼 키움)
        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path_first),
            "-i",
            str(input_path_second),
            "-filter_complex",
            f"[1:a]volume={gain_db}dB[a1];[0:a][a1]amix=inputs=2:normalize=0[outa]",
            "-map",
            "[outa]",
            str(output_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg mix/boost failed: {stderr.decode(errors='ignore')}")
