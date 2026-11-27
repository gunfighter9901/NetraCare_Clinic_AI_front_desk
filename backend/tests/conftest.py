from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.db import create_engine_for_url, create_session_factory, init_db


@pytest.fixture()
def engine():
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(engine):
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session


@pytest.fixture()
def session_factory(engine):
    return create_session_factory(engine)


@pytest.fixture()
def data_pack_path() -> Path:
    return Path(__file__).resolve().parents[2] / "Project_Resources" / "data-pack-Iteration_01"


@pytest.fixture()
def client(db: Session, data_pack_path: Path):
    from datetime import datetime

    from fastapi.testclient import TestClient

    from app.clock import FixedClock, get_clock
    from app.db import get_db
    from app.llm import RedFlagResult
    from app.loader import load_data_pack
    from app.main import app
    from app.routers.appointments import get_red_flag_checker

    load_data_pack(db, data_pack_path)

    def override_get_db():
        yield db

    def stub_checker(_text: str) -> RedFlagResult:
        return RedFlagResult(red_flag=False, category="none", why="test stub")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_clock] = lambda: FixedClock(datetime(2026, 11, 2, 10, 0))
    app.dependency_overrides[get_red_flag_checker] = lambda: stub_checker
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_db(db: Session, data_pack_path: Path, request: pytest.FixtureRequest):
    from app.loader import load_data_pack, load_past_visits, load_seed_appointments

    load_data_pack(db, data_pack_path)
    load_seed_appointments(db, data_pack_path / "stretch" / "appointments_seed.csv")
    # Iteration 4 agent scenarios require data pack 2 completed history.
    pack2_visits = (
        data_pack_path.parent / "data-pack-Iteration_02" / "past_visits.csv"
    )
    try:
        if pack2_visits.exists():
            load_past_visits(db, pack2_visits)
    except Exception:
        pass
    return db
