from sqlalchemy import Column, Integer, String, DateTime, Float
from db.connection import Base

class Transactions(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String(100))
    value = Column(Float)
    date = Column(DateTime)
    category = Column(String(100))

class Categories(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))