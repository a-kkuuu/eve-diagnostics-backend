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
    session = TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")
    
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

from app.models.user import User
from app.security import hash_password, create_access_token

@pytest.fixture
def test_user(db):
    user = User(email="normal_user@eve.com", password_hash=hash_password("password"), full_name="User", is_admin=False)
    db.add(user)
    db.commit()
    return user

@pytest.fixture
def admin_user(db):
    user = User(email="admin_test@eve.com", password_hash=hash_password("password"), full_name="Admin", is_admin=True)
    db.add(user)
    db.commit()
    return user

@pytest.fixture
def user_token(test_user):
    return create_access_token(test_user.id)

@pytest.fixture
def admin_token(admin_user):
    return create_access_token(admin_user.id)

@pytest.fixture
def auth_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}

@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
