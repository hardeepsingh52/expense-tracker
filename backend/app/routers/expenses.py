from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import engine
from ..models import Expense, ExpenseCreate, User
from ..security import get_current_user
from ..utils import utc_now

router = APIRouter(prefix="/expenses")


@router.post("/")
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


@router.get("/")
def read_expenses(current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        expenses = session.exec(select(Expense).where(Expense.user_id == current_user.id)).all()
        return expenses


@router.delete("/{expense_id}")
def delete_expense(expense_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        expense = session.exec(select(Expense).where(Expense.id == expense_id, Expense.user_id == current_user.id)).first()
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        session.delete(expense)
        session.commit()
        return {"message": "Expense deleted successfully"}


@router.put("/{expense_id}")
def update_expense(expense_id: int, expense_update: ExpenseCreate, current_user: User = Depends(get_current_user)):
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
