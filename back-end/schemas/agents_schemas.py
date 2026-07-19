import pydantic
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import Literal, List

class OrchestratorResponse(BaseModel):
    message: str
    type: Literal["check", "registry", "off-topic"]

CategoryType = Literal[
    "Aluguel", "Contas Básicas", "Internet e Telefone", "Seguros", "Pagamento de Dívidas", "Impostos", "Supermercado",
    "Alimentação", "Transporte", "Saúde e Farmácia", "Cuidados Pessoais", "Entretenimento", "Compras", "Assinaturas",
    "Exercícios e Esportes", "Hobbies", "Viagem", "Educação", "Manutenção da Casa", "Pets", "Presentes e Doações",
    "Eventos Especiais", "Emergências", "Fundo de Emergência", "Investimentos", "Outros"
]

class ExpenseItem(BaseModel):
    amount: int | None
    Category: CategoryType

class RecorderResponse(BaseModel):
    items: List[ExpenseItem]
