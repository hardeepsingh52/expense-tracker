from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field

from .utils import utc_now


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str
    hashed_password: str
    role: str = Field(default="user")  # "user" or "admin"


# Request body shape for signup/login (plain password, not stored directly)
class UserLogin(SQLModel):
    email: str
    password: str


class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=utc_now)


class ConversationMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id")
    role: str          # "system" | "user" | "assistant" | "tool"
    content: str
    tool_call_id: Optional[str] = Field(default=None)    # only set for role="tool"
    tool_calls_json: Optional[str] = Field(default=None)  # only set for role="assistant" when it made tool calls
    created_at: datetime = Field(default_factory=utc_now)


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
