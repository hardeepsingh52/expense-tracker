
# ... rest of your imports and code
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import SQLModel, Field, Session, create_engine, select
from contextlib import asynccontextmanager
import bcrypt
from typing import Optional
from jose import jwt
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
import json
import os

#client = OpenAI(
 #   base_url="https://integrate.api.nvidia.com/v1",
 #   api_key=os.environ["NVIDIA_API_KEY"]
#)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1/",
    api_key=os.environ["GROQ_API_KEY"]
)

def utc_now():
    return datetime.now(timezone.utc)

# --- Database setup ---
DATABASE_URL = "sqlite:///./expenses.db"
engine = create_engine(DATABASE_URL)

# --- JWT settings ---
SECRET_KEY = os.environ["SECRET_KEY"]
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
    role: str = Field(default="user")  # "user" or "admin"

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
    expire = utc_now() + timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
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


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            raise credentials_exception
        return user

def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user

@app.get("/admin")
def read_admin_data(current_user: User = Depends(get_current_admin_user)):
    with Session(engine) as session:
     return session.exec(select(User)).all()

@app.get("/me")
def read_current_user(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email, "id": current_user.id, "role": current_user.role}

class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    amount: float
    description: str
    category: str
    date: datetime = Field(default_factory=utc_now)


class ExpenseCreate(SQLModel):
    amount: float
    description: str
    category: str
    date: Optional[datetime] = None


@app.post("/expenses/")
def create_expense(expense: ExpenseCreate, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        new_expense = Expense(
            user_id=current_user.id,
            amount=expense.amount,
            description=expense.description,
            date=expense.date or utc_now(),
            category=expense.category
        )
        session.add(new_expense)
        session.commit()
        session.refresh(new_expense)
        return new_expense 


@app.get("/expenses/")
def read_expenses(current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        expenses = session.exec(select(Expense).where(Expense.user_id == current_user.id)).all()
        return expenses

@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        expense = session.exec(select(Expense).where(Expense.id == expense_id, Expense.user_id == current_user.id)).first()
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        session.delete(expense)
        session.commit()
        return {"message": "Expense deleted successfully"}

@app.put("/expenses/{expense_id}")
def update_expense(expense_id: int, expense_update: ExpenseCreate, current_user:    User = Depends(get_current_user)):
    with Session(engine) as session:
        expense = session.exec(select(Expense).where(Expense.id == expense_id, Expense.user_id == current_user.id)).first()
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        expense.amount = expense_update.amount
        expense.description = expense_update.description
        expense.category = expense_update.category
        expense.date = expense_update.date or utc_now()
        session.add(expense)
        session.commit()
        session.refresh(expense)
        return expense


def get_expenses_summary(user_id: int, category: Optional [str] = None) -> str:
    with Session(engine) as session:
        query = select(Expense).where(Expense.user_id == user_id)
        if category:
            query = query.where(Expense.category == category)
        expenses = session.exec(query).all()
        if not expenses:
           return "No expense found"
        
        total_amount = sum(expense.amount for expense in expenses)
        breakdown = "\n".join([f"- {e.category}: ${e.amount} {e.date} ({e.description or 'no description'})" for e in expenses])
        return f"Total: ${total_amount}\n\nDetails:\n{breakdown}"

expense_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_expenses_summary",
            "description": "Get a summary of the user's expenses, optionally filtered by category",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category to filter by, e.g. 'Food', 'Transport'"
                    }
                },
                "required": []
            }
        }
    }
]

@app.post("/ask")
def ask_about_expenses(question: dict, current_user: User = Depends(get_current_user)):
    user_question = question["question"]

    messages = [
        {"role": "user", "content": user_question}
    ]

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        tools=expense_tools,
        max_tokens=1000
    )

    reply = response.choices[0].message

    if reply.tool_calls:
        tool_call = reply.tool_calls[0]
        arguments = json.loads(tool_call.function.arguments)

        # We control user_id ourselves — never trust the model to supply it
        result = get_expenses_summary(user_id=current_user.id, category=arguments.get("category"))

        messages.append(reply)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result
        })

        final_response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            tools=expense_tools,
            max_tokens=1000
        )

        return {"answer": final_response.choices[0].message.content}

    return {"answer": reply.content}