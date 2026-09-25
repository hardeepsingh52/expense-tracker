from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import create_tables
from .routers import ask, auth, expenses


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("STARTUP: creating tables...")
    create_tables()
    print("STARTUP: tables created")
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(ask.router)
