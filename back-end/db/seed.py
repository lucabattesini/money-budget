from sqlalchemy.orm import Session
from .connection import LocalSession
from schemas.tables import Categories

default_categories = [
    "Aluguel", "Contas Básicas", "Internet e Telefone", "Seguros", "Pagamento de Dívidas", "Impostos", "Supermercado",
    "Alimentação", "Transporte", "Saúde e Farmácia", "Cuidados Pessoais", "Entretenimento", "Compras", "Assinaturas",
    "Exercícios e Esportes", "Hobbies", "Viagem", "Educação", "Manutenção da Casa", "Pets", "Presentes e Doações",
    "Eventos Especiais", "Emergências", "Fundo de Emergência", "Investimentos", "Outros"
]

def seed_categories():

    db: Session = LocalSession()
    
    try:
        for name in default_categories:

            exist = db.query(Categories).filter_by(name=name).first()
            if not exist:
                db.add(Categories(name=name))
        
        db.commit()
        print("Default categories created successfully")
    except Exception as e:
        db.rollback()
        print("Error to insert default categories", e)
    finally:
        db.close()

seed_categories()