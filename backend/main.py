from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .database import Base, engine, get_db
from . import crud, schemas, models
from .utils import get_usd_rate, generate_expenses_excel
from fastapi.responses import Response

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/expenses/", response_model=List[schemas.ExpenseDB])
def read_expenses(
        user_id: int,
        start_date: str = None,
        end_date: str = None,
        db: Session = Depends(get_db)
):
    """
    Отримати список витрат за датами (опційно).
    """
    s_date = None
    e_date = None
    from datetime import datetime

    if start_date:
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if end_date:
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    expenses = crud.get_expenses(db, user_id, s_date, e_date)
    return expenses


@app.post("/expenses/", response_model=schemas.ExpenseDB)
def create_new_expense(expense: schemas.ExpenseCreate, db: Session = Depends(get_db)):
    """
    Додати статтю витрат.
    """
    usd_rate = get_usd_rate()
    return crud.create_expense(db, expense, usd_rate)


@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, user_id: int, db: Session = Depends(get_db)):
    """
    Видалити статтю витрат за ID.
    """
    success = crud.delete_expense(db, expense_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Expense not found.")
    return {"status": "deleted"}


@app.put("/expenses/{expense_id}", response_model=schemas.ExpenseDB)
def edit_expense(expense_id: int, user_id: int, update_data: schemas.ExpenseUpdate, db: Session = Depends(get_db)):
    """
    Відредагувати статтю витрат за ID.
    """
    usd_rate = get_usd_rate()
    updated = crud.update_expense(db, expense_id, user_id, update_data, usd_rate)
    if not updated:
        raise HTTPException(status_code=404, detail="Expense not found.")
    return updated


@app.get("/expenses/report/")
def get_report(user_id: int, start_date: str, end_date: str, db: Session = Depends(get_db)):
    from datetime import datetime

    s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    e_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    expenses = crud.get_expenses(db, user_id, s_date, e_date)
    excel_data = generate_expenses_excel(expenses)  # Повертає bytes

    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=expenses_report.xlsx"}
    )
