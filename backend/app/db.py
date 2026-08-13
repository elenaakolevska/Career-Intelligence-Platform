from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Optional

from app.core.config import settings


def _resolve_db_url() -> str:
	if settings.test_database_url:
		return settings.test_database_url
	return settings.database_url


_engine: Optional[object] = None


def get_engine():
	global _engine
	if _engine is None:
		_engine = create_engine(_resolve_db_url(), echo=False)
	return _engine


def SessionLocal():
	engine = get_engine()
	return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


Base = declarative_base()
