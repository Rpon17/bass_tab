from pathlib import Path

def audio_path(raw_path: Path, asset_id: str ,audio_name: str) -> str:
    return str(raw_path /"assets"/asset_id /"audio"/ audio_name)


def tab_path(raw_path: Path, asset_id : str, tab_name: str) -> str:
    return str(raw_path /"assets"/asset_id /"tab"/ tab_name)