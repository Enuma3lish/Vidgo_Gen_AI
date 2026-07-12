from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import get_settings

settings = get_settings()

# 2026-07-12 perf audit #1: was echo=True (logged every SQL + params in prod —
# CPU/log-volume cost + query-data leak) with NO pool tuning. Now:
#   - echo gated on DEBUG so prod is quiet (set DEBUG=false in prod env).
#   - pool_pre_ping: Cloud SQL silently drops idle connections; without this
#     the next checkout hands back a dead socket → OperationalError. pre_ping
#     validates on checkout and transparently reconnects.
#   - pool_recycle 1800s: proactively retire connections before Cloud SQL's
#     server-side idle timeout can.
#   - explicit sizing: 10 + 20 overflow per instance (tune to Cloud SQL
#     max_connections ÷ max instance count).
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=bool(getattr(settings, "SQL_ECHO", False)),
    future=True,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
