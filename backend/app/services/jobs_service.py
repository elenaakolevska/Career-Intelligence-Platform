from sqlalchemy.orm import Session


class JobsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_jobs(self) -> list:
        return []
