# app/application/ports/spleeter_port.py
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class SpleeterPort(ABC):

	@abstractmethod
	async def split(
		self,
		*,
		input_wav_path: Path,
		output_dir: Path,
	) -> None:
		...
