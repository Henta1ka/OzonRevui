"""Database connection and session management"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# Подключение к БД (SQLite для разработки, PostgreSQL для production)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

# Фабрика сессий
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


class Base(DeclarativeBase):
    # Базовый класс для всех моделей
    pass


def get_db():
    # Зависимость для использования в endpoints'ах
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
