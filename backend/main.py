print("!!!!! THIS FILE IS RUNNING !!!!!")

from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
# ... rest of your imports and code
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from sqlmodel import SQLModel, Field, Session, create_engine, select
from contextlib import asynccontextmanager
import bcrypt
from typing import Optional
from jose import jwt


# --- Database setup ---
DATABASE_URL = "sqlite:///./expenses.db"
engine = create_engine(DATABASE_URL)

# --- JWT settings ---
SECRET_KEY = "change-this-to-something-random-and-secret"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


#----- Password Hash Setup ------

import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# --- User model ---
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str
    hashed_password: str

# --- Request body shape for signup (plain password, not stored directly) ---
class UserLogin(SQLModel):
    email: str
    password: str

def create_tables():
    SQLModel.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("STARTUP: creating tables...")
    create_tables()
    print("STARTUP: tables created")
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/signup")
def create_user(user: UserLogin):
    with Session(engine) as session:
     existing = session.exec(select(User).where(User.email == user.email)).first()
     if existing:
        raise HTTPException(status_code= 400, detail = "User already registered")

     hashed = hash_password(user.password)
     new_user = User(email=user.email, hashed_password = hashed)
     session.add(new_user)
     session.commit()
     session.refresh(new_user)

     return {"message": "User created cussessfully", "user_id": new_user.id}

# ---- LOGIN SETUP ----
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm = ALGORITHM)


@app.post("/login")
def login(user: UserLogin):
    with Session(engine) as session:
        db_user = session.exec(select(User).where(User.email == user.email)).first()

        if not db_user or not verify_password(user.password, db_user.hashed_password):
            raise HTTPException(status_code=401, detail = "Invalid user or password")

        token = create_access_token(data={"sub": db_user.email})
        return {"access_token": token, "token_type": "bearer"}