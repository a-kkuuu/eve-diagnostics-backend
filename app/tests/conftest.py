import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db, Base
from app.config import settings

TEST_DATABASE_URL = settings.database_url + "_test"

def create_test_db_if_not_exists():
    default_engine = create_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    try:
        with default_engine.connect() as conn:
            conn.execute(text("CREATE DATABASE eve_db_test"))
    except Exception as e:
        # Ignore if db already exists
        pass
    finally:
        default_engine.dispose()

create_test_db_if_not_exists()

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def db(setup_database):
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]
