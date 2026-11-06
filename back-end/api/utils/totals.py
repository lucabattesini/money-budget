"""What is left out of the totals by default (TKT-87).

A transfer between the person's own accounts and the payment of a card bill are not spending: the money only moved, and
the purchases on the card are counted by themselves. So a transaction in one of those categories starts out left out of
the totals, unless the person says otherwise. They can mark or unmark any transaction.

Pure names and one query; the migration that marked the existing ones (0020) spells the same two names out on its own.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from api.utils.category_names import name_key
from schemas.tables import Categories, CategoryGroups

UNCOUNTED_GROUP = "Transferências"
# The categories of that group that are not spending (the third, "Ajustes de saldo", is a correction and still counts)
UNCOUNTED_CATEGORIES = ("Transferência", "Pagamento de fatura do cartão")


def excluded_by_default(db: Session, category_ids) -> set[UUID]:
    """Which of these categories start out left out of the totals."""
    ids = {category_id for category_id in category_ids if category_id is not None}
    if not ids:
        return set()
    rows = (
        db.query(Categories.id, Categories.name)
        .join(CategoryGroups, Categories.group_id == CategoryGroups.id)
        .filter(Categories.id.in_(ids), CategoryGroups.name == UNCOUNTED_GROUP)
        .all()
    )
    names = {name_key(name) for name in UNCOUNTED_CATEGORIES}
    return {category_id for category_id, name in rows if name_key(name) in names}
