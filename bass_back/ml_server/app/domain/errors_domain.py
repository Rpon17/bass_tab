from __future__ import annotations


class DomainError(RuntimeError):
    pass


class InvalidStateTransition(DomainError):
    pass


class JobNotFoundError(Exception):
    """
    규약 : 만약 이 코드가 호출된다면 job_not_found를 상속자에게 올린다 
    """

    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(f"Job not found: {job_id}")

class InvalidAssetPath(Exception):
    
    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Path rule fail: {path}")