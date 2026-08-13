import os
import pytest
from sqlalchemy import create_engine, text


INTEGRATION_URL = os.getenv('INTEGRATION_DB_URL')


@pytest.mark.skipif(not INTEGRATION_URL, reason='Integration DB URL not provided')
def test_trivial_query_integration():
    engine = create_engine(INTEGRATION_URL)
    with engine.connect() as conn:
        res = conn.execute(text('SELECT 1')).scalar()
        assert res == 1
