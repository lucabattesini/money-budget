"""Make users.whatsapp_phone unique (one WhatsApp number, one account).

Existing numbers are first cleaned to digits only ("+55 (11) 99999-9999" -> "5511999999999"), the form the
API now stores. If several users ended up with the same number, the oldest account (lowest id) keeps it and
the others lose it (it becomes empty); they can set a number again from their account page. The downgrade
only drops the constraint: the cleaned and de-duplicated numbers are not restored.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

CONSTRAINT = "uq_users_whatsapp_phone"


def upgrade() -> None:
    op.execute(
        "UPDATE users SET whatsapp_phone = NULLIF(regexp_replace(whatsapp_phone, '[^0-9]', '', 'g'), '') "
        "WHERE whatsapp_phone IS NOT NULL"
    )
    op.execute(
        "UPDATE users SET whatsapp_phone = NULL WHERE whatsapp_phone IS NOT NULL AND id NOT IN "
        "(SELECT MIN(id) FROM users WHERE whatsapp_phone IS NOT NULL GROUP BY whatsapp_phone)"
    )
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_unique_constraints("users")}
    if CONSTRAINT not in existing:
        op.create_unique_constraint(CONSTRAINT, "users", ["whatsapp_phone"])


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "users", type_="unique")
