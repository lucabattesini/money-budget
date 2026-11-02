from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, func

from db.connection import Base


class TransactionDB(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    label = Column(String(100))
    value = Column(Integer)  # always positive, in cents; `type` says which way the money went
    type = Column(String(6), nullable=False, default="debit", server_default="debit")  # "debit" | "credit"
    transactioned_at = Column(DateTime)  # when the money moved (the user may change it)
    created_at = Column(DateTime, server_default=func.now())  # when the row was first saved
    updated_at = Column(DateTime)  # when the row was last edited; empty if never edited
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)


class Users(Base):
    __tablename__ = "users"
    # One WhatsApp number belongs to one account (several users may have no number: NULLs do not clash)
    __table_args__ = (UniqueConstraint("whatsapp_phone", name="uq_users_whatsapp_phone"),)

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


class ExportJobDB(Base):
    """A request to build a file with the user's data. The file is built in the background."""

    __tablename__ = "export_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    format = Column(String(10), nullable=False)  # "csv" | "xlsx"
    status = Column(String(10), nullable=False, default="queued")  # queued -> running -> done | failed
    filename = Column(String(100))
    media_type = Column(String(100))
    content = Column(LargeBinary)  # the finished file; kept for a day, then deleted
    error = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime)
