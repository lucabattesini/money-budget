from sqlalchemy import func, text
from sqlalchemy.orm import Session

from schemas.tables import Categories, CategoryGroups

from .connection import LocalSession
from .upgrade import MIGRATION_LOCK_ID

# The fixed set of groups, in the order they are shown, and the default categories of each.
DEFAULT_GROUPS: dict[str, list[str]] = {
    "Casa": ["Aluguel", "Contas Básicas", "Internet e Telefone", "Manutenção da Casa", "Pets"],
    "Alimentação": ["Supermercado", "Alimentação"],
    "Transporte": ["Transporte"],
    "Saúde e bem-estar": ["Saúde e Farmácia", "Cuidados Pessoais", "Exercícios e Esportes"],
    "Lazer": ["Entretenimento", "Hobbies", "Viagem", "Assinaturas", "Eventos Especiais"],
    "Educação": ["Educação"],
    "Compras e presentes": ["Compras", "Presentes e Doações"],
    "Finanças": ["Seguros", "Pagamento de Dívidas", "Impostos", "Emergências"],
    "Receitas": [
        "Salário",
        "Renda extra e freelance",
        "Rendimentos de investimentos",
        "Reembolsos",
        "Presentes recebidos",
        "Outras receitas",
    ],
    "Transferências": ["Transferência entre contas", "Pagamento de fatura do cartão", "Retirada e depósito"],
    "Investimentos": [
        "Investimentos",
        "Fundo de Emergência",
        "Renda fixa",
        "Ações e fundos",
        "Previdência privada",
        "Criptomoedas",
    ],
    "Outros": ["Outros"],
}

default_categories = [name for names in DEFAULT_GROUPS.values() for name in names]


def seed_categories():
    """Create the groups and the default categories that are missing. Safe to run any number of times."""

    db: Session = LocalSession()

    try:
        # Two API containers starting together must not seed at the same time (the same lock the upgrade uses,
        # released when this transaction ends)
        db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": MIGRATION_LOCK_ID})
        for group_name, category_names in DEFAULT_GROUPS.items():
            group = db.query(CategoryGroups).filter_by(name=group_name).first()
            if not group:
                group = CategoryGroups(name=group_name)
                db.add(group)
                db.flush()
            for name in category_names:
                # Only default categories count: a family may have its own category with the same name
                # (ignoring case, like the migration does when it groups the categories that already exist)
                exist = (
                    db.query(Categories)
                    .filter(func.lower(Categories.name) == name.lower(), Categories.family_id.is_(None))
                    .first()
                )
                if not exist:
                    db.add(Categories(name=name, group_id=group.id))

        db.commit()
        print("Default categories created successfully")
    except Exception:
        db.rollback()
        raise  # a failed seed must stop `db.upgrade && db.seed && uvicorn`, not be hidden
    finally:
        db.close()


if __name__ == "__main__":
    seed_categories()
