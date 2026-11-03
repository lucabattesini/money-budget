"""Development-only sample data: ~3 months of transactions for one user.

Log in with Google once so your user exists, then run inside the API container:
    docker compose exec api python -m db.seed_dev --email you@example.com [--reset]

The transactions are attached to the existing user with that email. The script
never creates a real user, because a pre-created row would clash with the
unique email on the first Google login.

Without --email it falls back to a demo user (demo@example.com). That user
cannot log in through Google, so the script prints a JWT for calling the API
directly instead.

Idempotent: transactions are only inserted if the user has none, unless
--reset is given (which deletes the user's family's transactions first).
"""

import argparse
import random
from datetime import datetime, timedelta

from api.utils.category_names import plain_name
from db.connection import LocalSession
from db.seed import seed_categories
from schemas.tables import Categories, Families, TransactionDB, Users

DEMO_EMAIL = "demo@example.com"

# (label, category, min cents, max cents, monthly occurrences)
TEMPLATES = [
    ("Aluguel", "Aluguel", 180000, 180000, 1),
    ("Conta de luz", "Luz e gás", 9000, 18000, 1),
    ("Internet", "Internet e TV", 11990, 11990, 1),
    ("Netflix", "Entretenimento e Lazer", 5590, 5590, 1),
    ("Spotify", "Entretenimento e Lazer", 2190, 2190, 1),
    ("Academia", "Academia e Fitness", 12900, 12900, 1),
    ("Supermercado", "Supermercado", 8000, 32000, 4),
    ("Almoço", "Restaurantes e Bares", 2500, 6500, 8),
    ("iFood", "Restaurantes e Bares", 3500, 9000, 3),
    ("Uber", "Táxi e apps de transporte", 1200, 4500, 5),
    ("Farmácia", "Médico", 2000, 15000, 2),
    ("Cinema", "Entretenimento e Lazer", 3000, 8000, 1),
    ("Roupas", "Compras", 8000, 25000, 1),
    ("Presente", "Presentes", 5000, 20000, 1),
]


def get_user(db, email: str) -> Users:
    user = db.query(Users).filter(Users.email == email).first()
    if user:
        return user
    if email != DEMO_EMAIL:
        raise SystemExit(f"No user with email {email}. Log in with Google once first.")
    family = Families()
    db.add(family)
    db.flush()
    user = Users(
        family_id=family.id, google_id="demo-google-id", name="Demo User", email=DEMO_EMAIL, last_login=datetime.now()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=DEMO_EMAIL)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    seed_categories()  # the sample data needs the default categories
    rng = random.Random(42)  # deterministic data
    db = LocalSession()
    try:
        user = get_user(db, args.email)
        existing = db.query(TransactionDB).filter(TransactionDB.family_id == user.family_id)
        if args.reset:
            existing.delete()
            db.commit()
        elif existing.count():
            print(f"{args.email} already has transactions; use --reset to replace them.")
            return

        # Default categories start with an emoji ("🏠 Aluguel"); the templates use the words
        categories = {plain_name(c.name): c.id for c in db.query(Categories).filter(Categories.family_id.is_(None))}
        today = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        rows = []
        for month_offset in range(3):
            for label, category, low, high, count in TEMPLATES:
                for _ in range(count):
                    day = today - timedelta(days=month_offset * 30 + rng.randint(0, 29))
                    rows.append(
                        TransactionDB(
                            family_id=user.family_id,
                            user_id=user.id,
                            label=label,
                            value=rng.randint(low // 10, high // 10) * 10,
                            transactioned_at=day,
                            category_id=categories[category],
                        )
                    )
        db.add_all(rows)
        db.commit()
        print(f"Inserted {len(rows)} transactions for {args.email} (user id {user.id})")

        if args.email == DEMO_EMAIL:
            from api.controllers.auth_controller import create_jwt

            print(f"JWT for API testing: {create_jwt(user.id)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
