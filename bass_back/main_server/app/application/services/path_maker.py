from pathlib import Path


def audio_path(raw_path: Path, audio_name: str) -> str:
    return str(raw_path /"audio"/ audio_name)


def tab_path(raw_path: Path, tab_name: str) -> str:
    return str(raw_path /"tab"/ tab_name)