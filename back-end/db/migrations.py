from sqlalchemy import inspect, text

from schemas import tables  # noqa: F401  (importing the models is what registers their tables for create_all)

from .connection import Base, engine

Base.metadata.create_all(bind=engine)


def migrate_transaction_category_to_fk():
    """Replace transactions.category (category id stored as text) with an integer category_id FK.

    Idempotent: does nothing on databases created after the change.
    """
    columns = {c["name"] for c in inspect(engine).get_columns("transactions")}
    if "category" not in columns:
        return

    with engine.begin() as conn:
        if "category_id" not in columns:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN category_id INTEGER REFERENCES categories(id)"))

        categories = conn.execute(text("SELECT id, name FROM categories")).all()
        ids = {c.id for c in categories}
        ids_by_name = {c.name.lower(): c.id for c in categories}
        fallback_id = ids_by_name.get("outros")

        # Old rows hold the id as text, but the assistant used to fall back to the category name
        rows = conn.execute(text("SELECT id, category FROM transactions")).all()
        for row in rows:
            raw = (row.category or "").strip()
            if raw.isdigit() and int(raw) in ids:
                category_id = int(raw)
            else:
                category_id = ids_by_name.get(raw.lower(), fallback_id)
            conn.execute(
                text("UPDATE transactions SET category_id = :category_id WHERE id = :id"),
                {"category_id": category_id, "id": row.id},
            )

        conn.execute(text("ALTER TABLE transactions DROP COLUMN category"))

    print(f"Migrated {len(rows)} transactions to category_id")


def migrate_add_transaction_type():
    """Add transactions.type ("debit" or "credit"). Existing rows were all expenses, so they become debits.

    Idempotent: does nothing when the column exists (including databases created after the change).
    """
    columns = {c["name"] for c in inspect(engine).get_columns("transactions")}
    if "type" in columns:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE transactions ADD COLUMN type VARCHAR(6) NOT NULL DEFAULT 'debit'"))
    print("Added transactions.type")


def migrate_transaction_timestamps():
    """Rename transactions.date to transactioned_at and add created_at / updated_at.

    Before this, `date` was always the moment the row was saved, so it is also a good value for
    created_at on old rows. updated_at stays empty (never edited). Idempotent.
    """
    columns = {c["name"] for c in inspect(engine).get_columns("transactions")}
    if {"transactioned_at", "created_at", "updated_at"} <= columns:
        return

    with engine.begin() as conn:
        if "date" in columns and "transactioned_at" not in columns:
            conn.execute(text("ALTER TABLE transactions RENAME COLUMN date TO transactioned_at"))
        if "created_at" not in columns:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN created_at TIMESTAMP DEFAULT now()"))
            conn.execute(text("UPDATE transactions SET created_at = transactioned_at"))
        if "updated_at" not in columns:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN updated_at TIMESTAMP"))
    print("Added transactions.transactioned_at, created_at and updated_at")


migrate_transaction_category_to_fk()
migrate_add_transaction_type()
migrate_transaction_timestamps()
