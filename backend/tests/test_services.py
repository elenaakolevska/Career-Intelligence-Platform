from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.services.user_service import UserService
from app.services.cv_service import CVService


def get_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_user_service_create_and_get():
    db = get_session()
    svc = UserService(db)
    user = svc.create_user(email='u@example.com', full_name='U')
    assert user.id is not None
    got = svc.get_user(user.id)
    assert got.email == 'u@example.com'


def test_cv_service_create_and_get():
    db = get_session()
    user_svc = UserService(db)
    user = user_svc.create_user(email='c@example.com')
    cv_svc = CVService(db)
    cv = cv_svc.create_cv(user_id=user.id, raw_text='hello')
    assert cv.id is not None
    got = cv_svc.get_cv(cv.id)
    assert got.user_id == user.id
