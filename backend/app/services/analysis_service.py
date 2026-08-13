from sqlalchemy.orm import Session


class AnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def analyze(self, cv_id: int) -> dict:
        return {'cv_id': cv_id, 'status': 'not_implemented'}
