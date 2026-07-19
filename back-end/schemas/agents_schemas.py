import pydantic
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import Literal

class OrchestratorResponse(BaseModel):
    message: str
    type: Literal["check", "registry", "off-topic"]

CategoryType = Literal[
    "Aluguel", "Contas Básicas", "Internet e Telefone", "Seguros", "Pagamento de Dívidas", "Impostos", "Supermercado",
    "Alimentação", "Transporte", "Saúde e Farmácia", "Cuidados Pessoais", "Entretenimento", "Compras", "Assinaturas",
    "Exercícios e Esportes", "Hobbies", "Viagem", "Educação", "Manutenção da Casa", "Pets", "Presentes e Doações",
    "Eventos Especiais", "Emergências", "Fundo de Emergência", "Investimentos", "Outros"
]

class RecorderResponse(BaseModel):
    amount: int | None
    Category: CategoryType
