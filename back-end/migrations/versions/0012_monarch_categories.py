"""Replace the default categories with the ones Monarch Money has, in Portuguese.

Before: 12 groups and 39 default categories made up for this app. After: 14 groups and 51 default categories
that mirror Monarch's (Receitas, Auto e Transporte, Moradia, Contas e Serviços, Alimentação...).

Nothing a family has is lost:
- Every old default category is renamed into the closest new one (`CATEGORY_MAP`). When several old ones point to the
  same new one (Hobbies, Assinaturas and Eventos Especiais all become "Entretenimento e Lazer") the first is kept,
  the transactions of the others are moved to it and the others are deleted.
- The categories a family made are not renamed. They move to the new group that replaces their old one
  (`GROUP_MAP`).
- The new default categories no old one turned into are created by the seed command (`python -m db.seed`).

The groups are replaced, in the order of the list below. The lists are a copy made on purpose, so this migration keeps
working whatever the app's list becomes later.

The downgrade puts the 12 old groups back. The merged categories cannot be told apart again, so a new default
category goes back to the old name it came from (the one with the same name, else the first in `CATEGORY_MAP`) and,
with nothing to go back to (such as "Caridade"), keeps its name in "Outros". Nothing is deleted and no transaction
moves.

Revision ID: 0012
Revises: 0011
"""

import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

GROUPS = {
    "Receitas": [
        "Salário",
        "Juros",
        "Renda de negócios",
        "Outras receitas",
    ],
    "Presentes e Doações": [
        "Caridade",
        "Presentes",
    ],
    "Auto e Transporte": [
        "Pagamento do veículo",
        "Transporte público",
        "Combustível",
        "Manutenção do veículo",
        "Estacionamento e pedágios",
        "Táxi e apps de transporte",
    ],
    "Moradia": [
        "Financiamento imobiliário",
        "Aluguel",
        "Reformas e melhorias",
    ],
    "Contas e Serviços": [
        "Coleta de lixo",
        "Água",
        "Luz e gás",
        "Internet e TV",
        "Telefone",
    ],
    "Alimentação": [
        "Supermercado",
        "Restaurantes e Bares",
        "Cafeterias",
    ],
    "Compras": [
        "Compras",
        "Roupas",
        "Móveis e utensílios",
        "Eletrônicos",
    ],
    "Viagem e Estilo de Vida": [
        "Viagem e Férias",
        "Entretenimento e Lazer",
        "Pessoal",
        "Pets",
        "Dinheiro para diversão",
    ],
    "Filhos": [
        "Cuidados com filhos",
        "Atividades infantis",
    ],
    "Educação": [
        "Financiamento estudantil",
        "Educação",
    ],
    "Saúde e Bem-estar": [
        "Médico",
        "Dentista",
        "Academia e Fitness",
    ],
    "Finanças": [
        "Pagamento de empréstimos",
        "Serviços financeiros e jurídicos",
        "Tarifas financeiras",
        "Saque e caixa eletrônico",
        "Seguros",
        "Impostos",
    ],
    "Outros": [
        "Sem categoria",
        "Cheque",
        "Diversos",
    ],
    "Transferências": [
        "Transferência",
        "Pagamento de fatura do cartão",
        "Ajustes de saldo",
    ],
}

# old default category (words only) -> the new default category it becomes
CATEGORY_MAP = {
    "Aluguel": "Aluguel",
    "Contas Básicas": "Luz e gás",
    "Internet e Telefone": "Internet e TV",
    "Manutenção da Casa": "Reformas e melhorias",
    "Pets": "Pets",
    "Supermercado": "Supermercado",
    "Alimentação": "Restaurantes e Bares",
    "Transporte": "Transporte público",
    "Saúde e Farmácia": "Médico",
    "Cuidados Pessoais": "Pessoal",
    "Exercícios e Esportes": "Academia e Fitness",
    "Entretenimento": "Entretenimento e Lazer",
    "Hobbies": "Entretenimento e Lazer",
    "Viagem": "Viagem e Férias",
    "Assinaturas": "Entretenimento e Lazer",
    "Eventos Especiais": "Entretenimento e Lazer",
    "Educação": "Educação",
    "Compras": "Compras",
    "Presentes e Doações": "Presentes",
    "Seguros": "Seguros",
    "Pagamento de Dívidas": "Pagamento de empréstimos",
    "Impostos": "Impostos",
    "Emergências": "Diversos",
    "Salário": "Salário",
    "Renda extra e freelance": "Renda de negócios",
    "Rendimentos de investimentos": "Juros",
    "Reembolsos": "Outras receitas",
    "Presentes recebidos": "Outras receitas",
    "Outras receitas": "Outras receitas",
    "Transferência entre contas": "Transferência",
    "Pagamento de fatura do cartão": "Pagamento de fatura do cartão",
    "Retirada e depósito": "Saque e caixa eletrônico",
    "Investimentos": "Transferência",
    "Fundo de Emergência": "Transferência",
    "Renda fixa": "Transferência",
    "Ações e fundos": "Transferência",
    "Previdência privada": "Transferência",
    "Criptomoedas": "Transferência",
    "Outros": "Sem categoria",
}

# old group -> the new group its categories made by a family go to
GROUP_MAP = {
    "Casa": "Moradia",
    "Alimentação": "Alimentação",
    "Transporte": "Auto e Transporte",
    "Saúde e bem-estar": "Saúde e Bem-estar",
    "Lazer": "Viagem e Estilo de Vida",
    "Educação": "Educação",
    "Compras e presentes": "Compras",
    "Finanças": "Finanças",
    "Receitas": "Receitas",
    "Transferências": "Transferências",
    "Investimentos": "Transferências",
    "Outros": "Outros",
}

EMOJIS = {
    "Salário": "💰",
    "Juros": "🏦",
    "Renda de negócios": "💼",
    "Outras receitas": "➕",
    "Caridade": "🤝",
    "Presentes": "🎁",
    "Pagamento do veículo": "🚘",
    "Transporte público": "🚌",
    "Combustível": "⛽",
    "Manutenção do veículo": "🔧",
    "Estacionamento e pedágios": "🅿️",
    "Táxi e apps de transporte": "🚕",
    "Financiamento imobiliário": "🏡",
    "Aluguel": "🏠",
    "Reformas e melhorias": "🛠️",
    "Coleta de lixo": "🗑️",
    "Água": "🚰",
    "Luz e gás": "💡",
    "Internet e TV": "📶",
    "Telefone": "📱",
    "Supermercado": "🛒",
    "Restaurantes e Bares": "🍽️",
    "Cafeterias": "☕",
    "Compras": "🛍️",
    "Roupas": "👕",
    "Móveis e utensílios": "🛋️",
    "Eletrônicos": "💻",
    "Viagem e Férias": "✈️",
    "Entretenimento e Lazer": "🎬",
    "Pessoal": "🧴",
    "Pets": "🐾",
    "Dinheiro para diversão": "🎉",
    "Cuidados com filhos": "🧸",
    "Atividades infantis": "⚽",
    "Financiamento estudantil": "🎓",
    "Educação": "📚",
    "Médico": "🩺",
    "Dentista": "🦷",
    "Academia e Fitness": "🏋️",
    "Pagamento de empréstimos": "💸",
    "Serviços financeiros e jurídicos": "⚖️",
    "Tarifas financeiras": "🧾",
    "Saque e caixa eletrônico": "🏧",
    "Seguros": "🛡️",
    "Impostos": "🏛️",
    "Sem categoria": "📦",
    "Cheque": "📝",
    "Diversos": "🔖",
    "Transferência": "🔄",
    "Pagamento de fatura do cartão": "💳",
    "Ajustes de saldo": "🧮",
}

# The groups and emojis before this revision (the old default categories of each)
OLD_GROUPS = {
    "Casa": [
        "Aluguel",
        "Contas Básicas",
        "Internet e Telefone",
        "Manutenção da Casa",
        "Pets",
    ],
    "Alimentação": [
        "Supermercado",
        "Alimentação",
    ],
    "Transporte": [
        "Transporte",
    ],
    "Saúde e bem-estar": [
        "Saúde e Farmácia",
        "Cuidados Pessoais",
        "Exercícios e Esportes",
    ],
    "Lazer": [
        "Entretenimento",
        "Hobbies",
        "Viagem",
        "Assinaturas",
        "Eventos Especiais",
    ],
    "Educação": [
        "Educação",
    ],
    "Compras e presentes": [
        "Compras",
        "Presentes e Doações",
    ],
    "Finanças": [
        "Seguros",
        "Pagamento de Dívidas",
        "Impostos",
        "Emergências",
    ],
    "Receitas": [
        "Salário",
        "Renda extra e freelance",
        "Rendimentos de investimentos",
        "Reembolsos",
        "Presentes recebidos",
        "Outras receitas",
    ],
    "Transferências": [
        "Transferência entre contas",
        "Pagamento de fatura do cartão",
        "Retirada e depósito",
    ],
    "Investimentos": [
        "Investimentos",
        "Fundo de Emergência",
        "Renda fixa",
        "Ações e fundos",
        "Previdência privada",
        "Criptomoedas",
    ],
    "Outros": [
        "Outros",
    ],
}

OLD_EMOJIS = {
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

# new group -> the old group its family-made categories go back to
GROUP_BACK = {
    "Moradia": "Casa",
    "Contas e Serviços": "Casa",
    "Auto e Transporte": "Transporte",
    "Alimentação": "Alimentação",
    "Compras": "Compras e presentes",
    "Presentes e Doações": "Compras e presentes",
    "Viagem e Estilo de Vida": "Lazer",
    "Filhos": "Outros",
    "Educação": "Educação",
    "Saúde e Bem-estar": "Saúde e bem-estar",
    "Finanças": "Finanças",
    "Receitas": "Receitas",
    "Outros": "Outros",
    "Transferências": "Transferências",
}

_DECORATION = {"So", "Sk", "Cf", "Mn", "Me", "Zs"}


def _words(name: str) -> str:
    """The name without the emoji it starts with, in lower case."""
    text = (name or "").strip()
    start = 0
    while start < len(text) and unicodedata.category(text[start]) in _DECORATION:
        start += 1
    return text[start:].strip().casefold()


def upgrade() -> None:
    conn = op.get_bind()

    # 1. The groups: set the old ones aside (the name is unique), create the new ones in order
    old_groups = dict(conn.execute(sa.text("SELECT name, id FROM category_groups")).all())
    conn.execute(sa.text("UPDATE category_groups SET name = '__old_' || id"))
    for name in GROUPS:
        conn.execute(sa.text("INSERT INTO category_groups (name) VALUES (:name)"), {"name": name})
    new_groups = dict(
        conn.execute(sa.text("SELECT name, id FROM category_groups WHERE left(name, 6) <> '__old_'")).all()
    )

    # 2. A family's categories go to the group that replaces their old one ("Outros" if the group is not known)
    for old_name, old_id in old_groups.items():
        target = new_groups[GROUP_MAP.get(old_name, "Outros")]
        conn.execute(
            sa.text("UPDATE categories SET group_id = :new WHERE group_id = :old AND family_id IS NOT NULL"),
            {"new": target, "old": old_id},
        )

    # 3. The old default categories become (or are merged into) the new ones
    by_words = {words.casefold(): new for words, new in CATEGORY_MAP.items()}
    group_of = {name: group for group, names in GROUPS.items() for name in names}
    by_words.update(
        {name.casefold(): name for name in group_of if name.casefold() not in by_words}
    )  # already a new name
    kept: dict[str, int] = {}  # new name -> id of the row that now holds it
    rows = conn.execute(sa.text("SELECT id, name FROM categories WHERE family_id IS NULL ORDER BY id")).all()
    for row in rows:
        new = by_words.get(_words(row.name))
        if new is None:
            # A default category the old list did not know: it keeps its name and goes to "Outros"
            conn.execute(
                sa.text("UPDATE categories SET group_id = :g WHERE id = :id"), {"g": new_groups["Outros"], "id": row.id}
            )
        elif new in kept:
            conn.execute(
                sa.text("UPDATE transactions SET category_id = :keep WHERE category_id = :gone"),
                {"keep": kept[new], "gone": row.id},
            )
            conn.execute(sa.text("DELETE FROM categories WHERE id = :id"), {"id": row.id})
        else:
            kept[new] = row.id
            conn.execute(
                sa.text("UPDATE categories SET name = :name, group_id = :g WHERE id = :id"),
                {"name": f"{EMOJIS[new]} {new}", "g": new_groups[group_of[new]], "id": row.id},
            )

    # 4. The old groups have nothing left
    conn.execute(sa.text("DELETE FROM category_groups WHERE left(name, 6) = '__old_'"))


def downgrade() -> None:
    conn = op.get_bind()
    new_groups = dict(conn.execute(sa.text("SELECT name, id FROM category_groups")).all())
    conn.execute(sa.text("UPDATE category_groups SET name = '__new_' || id"))
    for name in OLD_GROUPS:
        conn.execute(sa.text("INSERT INTO category_groups (name) VALUES (:name)"), {"name": name})
    old_groups = dict(
        conn.execute(sa.text("SELECT name, id FROM category_groups WHERE left(name, 6) <> '__new_'")).all()
    )

    for name, new_id in new_groups.items():
        conn.execute(
            sa.text("UPDATE categories SET group_id = :old WHERE group_id = :new AND family_id IS NOT NULL"),
            {"old": old_groups[GROUP_BACK.get(name, "Outros")], "new": new_id},
        )

    # For each new default category, the old one it goes back to: the one with the same name, else the first that became it
    back: dict[str, str] = {}
    for old_name, new_name in CATEGORY_MAP.items():
        if old_name == new_name:
            back[new_name.casefold()] = old_name
    for old_name, new_name in CATEGORY_MAP.items():
        back.setdefault(new_name.casefold(), old_name)
    old_group_of = {name: group for group, names in OLD_GROUPS.items() for name in names}
    for row in conn.execute(sa.text("SELECT id, name FROM categories WHERE family_id IS NULL")).all():
        old_name = back.get(_words(row.name))
        if old_name is None:
            conn.execute(
                sa.text("UPDATE categories SET group_id = :g WHERE id = :id"), {"g": old_groups["Outros"], "id": row.id}
            )
        else:
            conn.execute(
                sa.text("UPDATE categories SET name = :name, group_id = :g WHERE id = :id"),
                {"name": f"{OLD_EMOJIS[old_name]} {old_name}", "g": old_groups[old_group_of[old_name]], "id": row.id},
            )

    conn.execute(sa.text("DELETE FROM category_groups WHERE left(name, 6) = '__new_'"))
