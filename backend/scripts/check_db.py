from app.core.config import settings
from sqlalchemy import text
from sqlalchemy import create_engine


def check():
    url = settings.test_database_url or settings.database_url
    engine = create_engine(url)
    with engine.connect() as conn:
        r = conn.execute(text('SELECT 1'))
        print('SELECT 1 ->', r.scalar())


if __name__ == '__main__':
    check()
