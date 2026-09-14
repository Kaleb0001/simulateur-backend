from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings, normaliser_database_url

settings = get_settings()


def creer_engine(url: str) -> Engine:
    """Crée le moteur SQLAlchemy adapté à la base visée (PostgreSQL ou SQLite)."""
    url = normaliser_database_url(url)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(
        url,
        # Les colonnes DateTime sont naïves et contiennent de l'UTC : la
        # session doit l'être aussi pour que now() écrive la même chose.
        connect_args={"options": "-c timezone=UTC"},
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_secondes,
        pool_recycle=1800,
        pool_pre_ping=True,
    )


engine = creer_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
