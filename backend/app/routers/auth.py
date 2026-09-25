from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import engine
from ..models import User, UserLogin
from ..security import (
    create_access_token,
    get_current_admin_user,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter()


@router.post("/signup")
def create_user(user: UserLogin):
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == user.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="User already registered")

        hashed = hash_password(user.password)
        new_user = User(email=user.email, hashed_password=hashed)
        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        return {"message": "User created successfully", "user_id": new_user.id}


@router.post("/login")
def login(user: UserLogin):
    with Session(engine) as session:
        db_user = session.exec(select(User).where(User.email == user.email)).first()

        if not db_user or not verify_password(user.password, db_user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid user or password")

        token = create_access_token(data={"sub": db_user.email})
        return {"access_token": token, "token_type": "bearer"}


@router.get("/admin")
def read_admin_data(current_user: User = Depends(get_current_admin_user)):
    with Session(engine) as session:
        return session.exec(select(User)).all()


@router.get("/me")
def read_current_user(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email, "id": current_user.id, "role": current_user.role}
