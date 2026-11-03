from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, func

from db.connection import Base


class Families(Base):
    """The people who share one budget. Transactions, categories and exports belong to a family."""

    __tablename__ = "families"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now())
    abandoned_at = Column(DateTime, nullable=True)  # when its last person left; it is deleted 30 days later


class TransactionDB(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # who entered it; information, not a permission
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
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)  # a person is in exactly one family
    role = Column(String(10), nullable=False, default="owner", server_default="owner")  # "owner" | "member"
    # The family left behind when joining another one with the data kept there: the person can go back for 30 days
    previous_family_id = Column(Integer, ForeignKey("families.id"), nullable=True)
    google_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    picture = Column(String(255), nullable=True)
    whatsapp_phone = Column(String(30), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    last_login = Column(DateTime)


class FamilyInvites(Base):
    """A code that lets one signed-in person join a family. It works once and expires."""

    __tablename__ = "family_invites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    code_hash = Column(String(64), nullable=False, unique=True)  # the code itself is shown once and never stored
    code_hint = Column(String(4), nullable=False)  # its last characters, to tell codes apart in a list
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)


class Categories(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=True)  # NULL = default category, shared by all
    name = Column(String(100))


class ExportJobDB(Base):
    """A request to build a file with the family's data. The file is built in the background."""

    __tablename__ = "export_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)  # whose data goes in the file
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # only this person can get the file
    format = Column(String(10), nullable=False)  # "csv" | "xlsx"
    status = Column(String(10), nullable=False, default="queued")  # queued -> running -> done | failed
    filename = Column(String(100))
    media_type = Column(String(100))
    content = Column(LargeBinary)  # the finished file; kept for a day, then deleted
    error = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime)
