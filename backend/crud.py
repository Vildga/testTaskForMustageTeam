from sqlalchemy.orm import Session
from datetime import date
from . import models, schemas
from typing import List, Optional


def create_expense(db: Session, expense_data: schemas.ExpenseCreate, usd_rate: float) -> models.Expense:
    amount_usd = round(expense_data.amount_uah / usd_rate, 2)
    db_expense = models.Expense(
        user_id=expense_data.user_id,
        title=expense_data.title,
        date=expense_data.date,
        amount_uah=expense_data.amount_uah,
        amount_usd=amount_usd
    )
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


def get_expenses(
    db: Session,
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[models.Expense]:
    query = db.query(models.Expense).filter(models.Expense.user_id == user_id)
    if start_date:
        query = query.filter(models.Expense.date >= start_date)
    if end_date:
        query = query.filter(models.Expense.date <= end_date)
    return query.order_by(models.Expense.date).all()


def get_expense_by_id(db: Session, expense_id: int, user_id: int):
    return db.query(models.Expense).filter(models.Expense.id == expense_id, models.Expense.user_id == user_id).first()


def delete_expense(db: Session, expense_id: int, user_id: int):
    expense = get_expense_by_id(db, expense_id, user_id)
    if expense:
        db.delete(expense)
        db.commit()
        return True
    return False


def update_expense(db: Session, expense_id: int, user_id: int, expense_data: schemas.ExpenseUpdate, usd_rate: float):
    expense = get_expense_by_id(db, expense_id, user_id)
    if not expense:
        return None

    if expense_data.title is not None:
        expense.title = expense_data.title
    if expense_data.date is not None:
        expense.date = expense_data.date
    if expense_data.amount_uah is not None:
        expense.amount_uah = expense_data.amount_uah
        expense.amount_usd = round(expense_data.amount_uah / usd_rate, 2)

    db.commit()
    db.refresh(expense)
    return expense

