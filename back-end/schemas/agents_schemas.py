# pyrefly: ignore [missing-import]
from datetime import date as Date  # aliased: a field below is also called "date"
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class OrchestratorResponse(BaseModel):
    message: str
    type: Literal["check", "registry", "off-topic"]


# The default categories the assistant can pick (not income or transfers: it registers expenses). A test keeps
# this in step with db/seed.py.
CategoryType = Literal[
    "Caridade",
    "Presentes",
    "Pagamento do veículo",
    "Transporte público",
    "Combustível",
    "Manutenção do veículo",
    "Estacionamento e pedágios",
    "Táxi e apps de transporte",
    "Financiamento imobiliário",
    "Aluguel",
    "Reformas e melhorias",
    "Coleta de lixo",
    "Água",
    "Luz e gás",
    "Internet e TV",
    "Telefone",
    "Supermercado",
    "Restaurantes e Bares",
    "Cafeterias",
    "Compras",
    "Roupas",
    "Móveis e utensílios",
    "Eletrônicos",
    "Viagem e Férias",
    "Entretenimento e Lazer",
    "Pessoal",
    "Pets",
    "Dinheiro para diversão",
    "Cuidados com filhos",
    "Atividades infantis",
    "Financiamento estudantil",
    "Educação",
    "Médico",
    "Dentista",
    "Academia e Fitness",
    "Pagamento de empréstimos",
    "Serviços financeiros e jurídicos",
    "Tarifas financeiras",
    "Saque e caixa eletrônico",
    "Seguros",
    "Impostos",
    "Sem categoria",
    "Cheque",
    "Diversos",
]

# --- Recorder tool (record_expenses) ---


class ExpenseItem(BaseModel):
    amount: float = Field(gt=0)  # reais, e.g. 12.5
    category: CategoryType
    description: str = Field(min_length=1, max_length=100)
    date: Optional[Date] = None  # defaults to today
    merchant: Optional[str] = Field(None, max_length=100)  # only asked for while the family has merchants on


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
    merchants: Optional[List[str]] = None  # names of merchants; only offered while the family has them on


class ListTransactionsArgs(QueryFiltersArgs):
    order_by: Literal["date", "amount"] = "date"
    order_dir: Literal["asc", "desc"] = "desc"
    limit: int = Field(20, ge=1, le=200)


class SummarizeTransactionsArgs(QueryFiltersArgs):
    group_by: Optional[Literal["category", "merchant", "day", "month", "year", "weekday"]] = None


class ToolCall(BaseModel):
    name: str
    args: dict[str, Any]


class QueryResponse(BaseModel):
    tool_calls: List[ToolCall]


class SecretaryResponse(BaseModel):
    reply: str
