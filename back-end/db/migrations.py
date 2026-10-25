from sqlalchemy import inspect, text
from .connection import Base, engine
from schemas.tables import TransactionDB, Categories, Users

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


migrate_transaction_category_to_fk()
