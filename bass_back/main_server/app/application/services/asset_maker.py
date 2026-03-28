from pathlib import Path

def audio_path_maker(raw_path: str | Path) -> str:

    path_str = str(raw_path)
    
    standardized_path = path_str.replace("/", "\\")
    
    return standardized_path

raw = r"https:\supuaxfcapguefgvreoi.supabase.co\storage\v1\object\public\bass_project\results\3e0dbf9e23d04e06ba3d08cabbaf5cff\assets\fb1c53f8ddef4c71a9b096fc5964aa66\audio\bass_only.mp3"

converted = audio_path_maker(raw)
print(f"변환 전: {raw}")
print(f"변환 후: {converted}")