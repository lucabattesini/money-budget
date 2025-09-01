from sqlalchemy import Column, Integer, String, DateTime, Boolean, func, ForeignKey
from db.connection import Base

class Transactions(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    label = Column(String(100))
    value = Column(Integer)
    date = Column(DateTime)
    category_id = Column(String(100))

# Relate transactions column to user

class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    last_login = Column(DateTime)
    is_active = Column(Boolean, server_default=False)

class Categories(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    label = Column(String(100))