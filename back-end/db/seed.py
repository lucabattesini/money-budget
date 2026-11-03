from sqlalchemy import text
from sqlalchemy.orm import Session

from api.utils.category_names import same_name
from schemas.tables import Categories, CategoryGroups

from .connection import LocalSession
from .upgrade import MIGRATION_LOCK_ID

# The fixed set of groups, in the order they are shown, and the default categories of each. They mirror the default
# categories of Monarch Money, in Portuguese.
DEFAULT_GROUPS: dict[str, list[str]] = {
    "Receitas": ["Salário", "Juros", "Renda de negócios", "Outras receitas"],
    "Presentes e Doações": ["Caridade", "Presentes"],
    "Auto e Transporte": [
        "Pagamento do veículo",
        "Transporte público",
        "Combustível",
        "Manutenção do veículo",
        "Estacionamento e pedágios",
        "Táxi e apps de transporte",
    ],
    "Moradia": ["Financiamento imobiliário", "Aluguel", "Reformas e melhorias"],
    "Contas e Serviços": ["Coleta de lixo", "Água", "Luz e gás", "Internet e TV", "Telefone"],
    "Alimentação": ["Supermercado", "Restaurantes e Bares", "Cafeterias"],
    "Compras": ["Compras", "Roupas", "Móveis e utensílios", "Eletrônicos"],
    "Viagem e Estilo de Vida": [
        "Viagem e Férias",
        "Entretenimento e Lazer",
        "Pessoal",
        "Pets",
        "Dinheiro para diversão",
    ],
    "Filhos": ["Cuidados com filhos", "Atividades infantis"],
    "Educação": ["Financiamento estudantil", "Educação"],
    "Saúde e Bem-estar": ["Médico", "Dentista", "Academia e Fitness"],
    "Finanças": [
        "Pagamento de empréstimos",
        "Serviços financeiros e jurídicos",
        "Tarifas financeiras",
        "Saque e caixa eletrônico",
        "Seguros",
        "Impostos",
    ],
    "Outros": ["Sem categoria", "Cheque", "Diversos"],
    "Transferências": ["Transferência", "Pagamento de fatura do cartão", "Ajustes de saldo"],
}

default_categories = [name for names in DEFAULT_GROUPS.values() for name in names]

# The emoji each default category starts with. It is part of the stored name ("🛒 Supermercado"), not a field.
DEFAULT_EMOJIS: dict[str, str] = {
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


def display_name(name: str) -> str:
    """The name a default category is stored under: its emoji, a space, then the name."""
    return f"{DEFAULT_EMOJIS[name]} {name}"


def seed_categories():
    """Create the groups and the default categories that are missing. Safe to run any number of times."""

    db: Session = LocalSession()

    try:
        # Two API containers starting together must not seed at the same time (the same lock the upgrade uses,
        # released when this transaction ends)
        db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": MIGRATION_LOCK_ID})
        for position, (group_name, category_names) in enumerate(DEFAULT_GROUPS.items(), start=1):
            group = db.query(CategoryGroups).filter_by(name=group_name).first()
            if not group:
                # A new group takes the place of the list above; an existing one keeps the position the database gives it
                group = CategoryGroups(name=group_name, position=position)
                db.add(group)
                db.flush()
            for name in category_names:
                # Only default categories count: a family may have its own category with the same name. Names are
                # compared by their words, so a default stored with or without its emoji is found either way.
                defaults = db.query(Categories).filter(Categories.family_id.is_(None))
                if not any(same_name(category.name, name) for category in defaults):
                    db.add(Categories(name=display_name(name), group_id=group.id))

        db.commit()
        print("Default categories created successfully")
    except Exception:
        db.rollback()
        raise  # a failed seed must stop `db.upgrade && db.seed && uvicorn`, not be hidden
    finally:
        db.close()


if __name__ == "__main__":
    seed_categories()
