# main_server/app/domain/errors.py
from __future__ import annotations
from pathlib import Path

class InvalidAssetPath(Exception):
    """  
        경로 오류가 나면 path반환
    """
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Job not found: {self.path}")
        
        
class JobNotFoundError(Exception):
    """
    규약 : 만약 이 코드가 호출된다면 job_not_found를 상속자에게 올린다 
    """

    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(f"Job not found: {job_id}")
