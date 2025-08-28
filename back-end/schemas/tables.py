from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean
from db.connection import Base

class Transactions(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100))
    label = Column(String(100))
    value = Column(Float)
    date = Column(DateTime)
    category = Column(String(100))
    type = Column(String(100))

class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    email = Column(String(100))
    password = Column(String(100))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    last_login = Column(DateTime)
    is_active = Boolean()

class Categories(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100))
    name = Column(String(100))