from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from langchain_core.runnables import Runnable
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# LLM stub — autouse so no test can ever reach a real Ollama
# ---------------------------------------------------------------------------


class FakeLLMController:
    """Per-test handle to configure the stubbed LLM's output or error."""

    def __init__(self):
        self.chunks: list[str] = ["• un\n", "• deux\n", "• trois\n"]
        self.error: Exception | None = None

    def build(self) -> Runnable:
        return _ControlledFakeLLM(self)


class _ControlledFakeLLM(Runnable):
    def __init__(self, ctrl: FakeLLMController):
        self._ctrl = ctrl

    def invoke(self, input, config=None, **kwargs) -> str:
        if self._ctrl.error:
            raise self._ctrl.error
        return "".join(self._ctrl.chunks)

    async def astream(self, input, config=None, **kwargs):
        if self._ctrl.error:
            raise self._ctrl.error
        for chunk in self._ctrl.chunks:
            yield chunk


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    """Autouse: patches app.summarizer.get_llm for every test."""
    ctrl = FakeLLMController()
    monkeypatch.setattr("app.summarizer.get_llm", ctrl.build)
    return ctrl


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncIterator[AsyncSession]:
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_worker_state():
    from app import worker

    worker._progress.clear()
    worker._listeners.clear()
    yield
    worker._progress.clear()
    worker._listeners.clear()
