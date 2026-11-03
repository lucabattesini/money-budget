"""Give the default categories an emoji, as part of their name ("Supermercado" -> "🛒 Supermercado").

Only default categories (no family) are renamed, and only the ones this list knows and that do not already start
with an emoji. A family's own categories are never touched: they have whatever name the family gave them. The
mapping is a copy made on purpose, so this migration keeps working whatever the app's list becomes later.

Names that were already stored keep working everywhere: the app compares category names by their words only, so
the assistant, the duplicate check and the import still find "Supermercado" when the stored name is
"🛒 Supermercado". Transactions point to categories by id and are not affected.

The downgrade removes the emoji and the space from the names this list knows.

Revision ID: 0011
Revises: 0010
"""

import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

EMOJIS = {
    "Aluguel": "🏠",
    "Contas Básicas": "💡",
    "Internet e Telefone": "📶",
    "Manutenção da Casa": "🔧",
    "Pets": "🐾",
    "Supermercado": "🛒",
    "Alimentação": "🍽️",
    "Transporte": "🚗",
    "Saúde e Farmácia": "💊",
    "Cuidados Pessoais": "🧴",
    "Exercícios e Esportes": "🏋️",
    "Entretenimento": "🎬",
    "Hobbies": "🎨",
    "Viagem": "✈️",
    "Assinaturas": "📺",
    "Eventos Especiais": "🎉",
    "Educação": "🎓",
    "Compras": "🛍️",
    "Presentes e Doações": "🎁",
    "Seguros": "🛡️",
    "Pagamento de Dívidas": "💸",
    "Impostos": "🧾",
    "Emergências": "🚨",
    "Salário": "💰",
    "Renda extra e freelance": "💼",
    "Rendimentos de investimentos": "📈",
    "Reembolsos": "↩️",
    "Presentes recebidos": "🎀",
    "Outras receitas": "➕",
    "Transferência entre contas": "🔄",
    "Pagamento de fatura do cartão": "💳",
    "Retirada e depósito": "🏧",
    "Investimentos": "💹",
    "Fundo de Emergência": "🏦",
    "Renda fixa": "🏛️",
    "Ações e fundos": "📊",
    "Previdência privada": "👴",
    "Criptomoedas": "🪙",
    "Outros": "📦",
}

_DECORATION = {"So", "Sk", "Cf", "Mn", "Me", "Zs"}


def _starts_with_emoji(name: str) -> bool:
    return bool(name) and (unicodedata.category(name[0]) in _DECORATION)


def upgrade() -> None:
    conn = op.get_bind()
    by_words = {words.casefold(): emoji for words, emoji in EMOJIS.items()}
    for row in conn.execute(sa.text("SELECT id, name FROM categories WHERE family_id IS NULL")).all():
        name = (row.name or "").strip()
        emoji = by_words.get(name.casefold())
        if emoji is not None and not _starts_with_emoji(name):
            conn.execute(
                sa.text("UPDATE categories SET name = :name WHERE id = :id"), {"name": f"{emoji} {name}", "id": row.id}
            )


def downgrade() -> None:
    conn = op.get_bind()
    prefixes = {f"{emoji} " for emoji in EMOJIS.values()}
    for row in conn.execute(sa.text("SELECT id, name FROM categories WHERE family_id IS NULL")).all():
        for prefix in prefixes:
            if (row.name or "").startswith(prefix):
                conn.execute(
                    sa.text("UPDATE categories SET name = :name WHERE id = :id"),
                    {"name": row.name[len(prefix) :], "id": row.id},
                )
                break
