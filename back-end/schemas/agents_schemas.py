# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from typing import Literal, List, Optional, Any
from datetime import date as Date  # aliased: a field below is also called "date"

class OrchestratorResponse(BaseModel):
    message: str
    type: Literal["check", "registry", "off-topic"]

CategoryType = Literal[
    "Aluguel", "Contas Básicas", "Internet e Telefone", "Seguros", "Pagamento de Dívidas", "Impostos", "Supermercado",
    "Alimentação", "Transporte", "Saúde e Farmácia", "Cuidados Pessoais", "Entretenimento", "Compras", "Assinaturas",
    "Exercícios e Esportes", "Hobbies", "Viagem", "Educação", "Manutenção da Casa", "Pets", "Presentes e Doações",
    "Eventos Especiais", "Emergências", "Fundo de Emergência", "Investimentos", "Outros"
]

# --- Recorder tool (record_expenses) ---

class ExpenseItem(BaseModel):
    amount: float = Field(gt=0)  # reais, e.g. 12.5
    category: CategoryType
    description: str = Field(min_length=1, max_length=100)
    date: Optional[Date] = None  # defaults to today

class RecordExpensesArgs(BaseModel):
    items: List[ExpenseItem]

class RecorderResponse(BaseModel):
    items: List[ExpenseItem]
    reply: Optional[str] = None  # text the model sent instead of / alongside the tool call

# --- Query tools (list_transactions / summarize_transactions) ---

class QueryFiltersArgs(BaseModel):
    start_date: Optional[Date] = None
    end_date: Optional[Date] = None
    categories: Optional[List[CategoryType]] = None
    exclude_categories: Optional[List[CategoryType]] = None
    search: Optional[str] = None
    min_amount: Optional[float] = Field(None, ge=0)  # reais
    max_amount: Optional[float] = Field(None, ge=0)  # reais
    weekdays: Optional[List[int]] = None  # 0 = Sunday ... 6 = Saturday

class ListTransactionsArgs(QueryFiltersArgs):
    order_by: Literal["date", "amount"] = "date"
    order_dir: Literal["asc", "desc"] = "desc"
    limit: int = Field(20, ge=1, le=200)

class SummarizeTransactionsArgs(QueryFiltersArgs):
    group_by: Optional[Literal["category", "day", "month", "year", "weekday"]] = None

class ToolCall(BaseModel):
    name: str
    args: dict[str, Any]

class QueryResponse(BaseModel):
    tool_calls: List[ToolCall]

class SecretaryResponse(BaseModel):
    reply: str
