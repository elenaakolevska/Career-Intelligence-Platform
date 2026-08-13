from sqlalchemy.orm import Session


class InterviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def start_session(self, user_id: int) -> dict:
        return {'session_id': 0, 'user_id': user_id}
