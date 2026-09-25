from sqlmodel import SQLModel, create_engine

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)


def create_tables():
    SQLModel.metadata.create_all(engine)
