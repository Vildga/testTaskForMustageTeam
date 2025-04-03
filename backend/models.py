from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey
from .database import Base
from sqlalchemy import BigInteger


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False)
    title = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    amount_uah = Column(Float, nullable=False)
    amount_usd = Column(Float, nullable=False)
