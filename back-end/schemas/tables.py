from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from db.connection import Base


class TransactionDB(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    label = Column(String(100))
    value = Column(Integer)  # always positive, in cents; `type` says which way the money went
    type = Column(String(6), nullable=False, default="debit", server_default="debit")  # "debit" | "credit"
    date = Column(DateTime)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    picture = Column(String(255), nullable=True)
    whatsapp_phone = Column(String(30), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    last_login = Column(DateTime)


class Categories(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(100))
