from pydantic import BaseModel
from datetime import date
from typing import Optional


class ExpenseBase(BaseModel):
    title: str
    date: date
    amount_uah: float


class ExpenseCreate(ExpenseBase):
    user_id: int


class ExpenseUpdate(BaseModel):
    title: Optional[str] = None
    date: Optional[date] = None
    amount_uah: Optional[float] = None


class ExpenseDB(BaseModel):
    id: int
    user_id: int
    title: str
    date: date
    amount_uah: float
    amount_usd: float

    class Config:
        orm_mode = True
