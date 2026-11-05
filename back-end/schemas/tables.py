from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    select,
)

from db.connection import Base


class Families(Base):
    """The people who share one budget. Transactions, categories and exports belong to a family."""

    __tablename__ = "families"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now())
    abandoned_at = Column(DateTime, nullable=True)  # when its last person left; it is deleted 30 days later
    # How the family sees amounts and dates, and the language the assistant answers in (see schemas/family_settings.py)
    currency = Column(String(3), nullable=False, default="BRL", server_default="BRL")
    language = Column(String(2), nullable=False, default="pt", server_default="pt")
    # Where the family lives: "now" is read on this clock, and a transaction's time is the wall-clock time there (TKT-65)
    timezone = Column(String(40), nullable=False, default="America/Sao_Paulo", server_default="America/Sao_Paulo")


class TransactionDB(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False
    )  # who it belongs to (who paid): a member of the family, whoever added it unless changed; not a permission
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


FALLBACK_GROUP = "Outros"  # where a category goes when nobody says which group it belongs to


class CategoryGroups(Base):
    """A heading the categories are listed under (Casa, Lazer...). The same fixed set for everyone."""

    __tablename__ = "category_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    # The place of the group in every list (1 is first). The order is data, not the order the rows were created in
    position = Column(Integer, nullable=False)


def _fallback_group_id(context) -> int:
    """The default group of a new category: "Outros". Runs inside the insert, on its own connection."""
    group_id = context.connection.execute(
        select(CategoryGroups.id).where(CategoryGroups.name == FALLBACK_GROUP)
    ).scalar()
    if group_id is None:
        raise RuntimeError(
            f'The category group "{FALLBACK_GROUP}" does not exist, so a category without a group cannot be saved. '
            "Run `python -m db.upgrade`, which creates the groups."
        )
    return group_id


class Categories(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=True)  # NULL = default category, shared by all
    name = Column(String(100))
    # Every category has exactly one group; without one it goes to "Outros"
    group_id = Column(Integer, ForeignKey("category_groups.id"), nullable=False, default=_fallback_group_id)


class Budgets(Base):
    """How much a family plans to spend in a category from one month on (integer cents, like every amount).

    A plan stays in force until a later month changes it, so a month with no row of its own uses the latest earlier
    row. A row of 0 means "nothing from this month on"."""

    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("family_id", "category_id", "month", name="uq_budgets_family_category_month"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    month = Column(Date, nullable=False)  # always the first day of the month
    amount = Column(Integer, nullable=False)  # cents; 0 stops the plan from this month on


class ImportJobDB(Base):
    """A spreadsheet of transactions on its way into the family's data, in steps.

    The file is read when it is uploaded and kept here ("staged") while the person says which column is which and
    settles the categories the file mentions that the family does not have yet. Only then is it queued and imported,
    in one go, in the background.
    """

    __tablename__ = "import_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)  # where the transactions go
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # who uploaded it; only they can follow it
    status = Column(String(10), nullable=False, default="staged")  # staged -> queued -> running -> done | failed
    filename = Column(String(255))  # the name of the uploaded file, to talk about it
    columns = Column(JSON)  # the names in the first row of the file, in order
    raw_rows = Column(JSON)  # what the file holds (see import_service.encode_cell); dropped when the job ends
    column_map = Column(JSON)  # {field: position of its column in the file, or null}; set once the person matched them
    rows = Column(
        JSON
    )  # the checked rows, [{"row", "date", "label", "value", "type", "category"}]; set with column_map
    category_map = Column(JSON)  # {name in the file: id of the category the person chose for it}
    total_rows = Column(Integer)
    imported_count = Column(Integer)
    skipped = Column(JSON)  # the rows left out because the family already had them
    error = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())  # when the file was uploaded
    queued_at = Column(DateTime)  # when the person confirmed; a job queued or running for too long is stuck
    finished_at = Column(DateTime)


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
