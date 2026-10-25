import json
from datetime import datetime, date
from pydantic import ValidationError
from graph.state import AssistantState
from agents.orchestrator.run import run_orchestrator
from agents.query.run import run_query
from agents.query.tools import LIST_TRANSACTIONS, SUMMARIZE_TRANSACTIONS
from agents.recorder.run import run_recorder
from agents.secretary.run import run_secretary
from api.repositories.transactions_repo import create_transaction, list_transactions, aggregate_transactions
from api.repositories.categories_repo import get_category_by_name
from schemas.tables_schemas import Transaction, TransactionFilters
from schemas.agents_schemas import ToolCall, QueryFiltersArgs, ListTransactionsArgs, SummarizeTransactionsArgs

# Same order as SQL's day-of-week: 0 = Sunday
SQL_WEEKDAY_NAMES = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"]

def _format_brl(amount: float) -> str:
    return "R$ " + f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _to_cents(amount: float | None) -> int | None:
    return None if amount is None else round(amount * 100)

def _category_ids(names: list[str] | None) -> list[int] | None:
    if not names:
        return None
    # An unknown name maps to -1 so it matches nothing instead of silently widening the filter
    return [cat.id if (cat := get_category_by_name(name)) else -1 for name in names]

def _to_filters(args: QueryFiltersArgs) -> TransactionFilters:
    return TransactionFilters(
        start_date=args.start_date,
        end_date=args.end_date,
        category_ids=_category_ids(args.categories),
        exclude_category_ids=_category_ids(args.exclude_categories),
        search=args.search,
        min_value=_to_cents(args.min_amount),
        max_value=_to_cents(args.max_amount),
        weekdays=args.weekdays,
    )

def _run_query_tool(call: ToolCall, user_id: int) -> dict:
    """Execute one query tool call for the user and return its result with amounts in reais."""
    try:
        if call.name == LIST_TRANSACTIONS:
            args = ListTransactionsArgs(**call.args)
            rows = list_transactions(
                user_id,
                _to_filters(args),
                order_by="value" if args.order_by == "amount" else "date",
                order_dir=args.order_dir,
                limit=args.limit,
            )
            result = [
                {
                    "description": t.label,
                    "amount": t.value / 100,
                    "date": t.date.date().isoformat() if t.date else None,
                    "category": t.category_name,
                }
                for t in rows
            ]
        elif call.name == SUMMARIZE_TRANSACTIONS:
            args = SummarizeTransactionsArgs(**call.args)
            rows = aggregate_transactions(user_id, _to_filters(args), args.group_by)
            result = []
            for row in rows:
                item = {}
                if args.group_by == "category":
                    item["category"] = row.category_name
                elif args.group_by == "weekday":
                    item["weekday"] = SQL_WEEKDAY_NAMES[row.weekday]
                elif args.group_by:
                    item["period"] = row.period
                item.update(
                    total=row.total / 100,
                    count=row.count,
                    average=round(row.average / 100, 2),
                    max=row.max / 100,
                )
                result.append(item)
        else:
            return {"tool": call.name, "error": "Unknown tool"}
    except (ValidationError, ValueError) as e:
        print("INVALID QUERY TOOL ARGS:", call, e)
        return {"tool": call.name, "error": "Invalid filters"}

    return {"tool": call.name, "filters": args.model_dump(mode="json", exclude_none=True), "result": result}

def node_orchestrator(state: AssistantState):
    response = run_orchestrator(state["user_message"])
    return {"intent": response.type}

def node_recorder(state: AssistantState):
    response = run_recorder(state["user_message"])
    now = datetime.now()

    registered = []
    for item in response.items:
        cat_obj = get_category_by_name(item.category) or get_category_by_name("Outros")
        # Keep the current time so same-day ordering still makes sense; never store future dates
        expense_date = item.date if item.date and item.date <= date.today() else now.date()

        t = Transaction(
            label=item.description,
            value=round(item.amount * 100),
            category_id=cat_obj.id,
            date=datetime.combine(expense_date, now.time()),
        )
        create_transaction(t, state["user_id"])
        registered.append(
            f"• {_format_brl(item.amount)} em {cat_obj.name} ({item.description}, {expense_date.strftime('%d/%m')})"
        )

    parts = []
    if registered:
        parts.append("Registrado!\n" + "\n".join(registered))
    if response.reply:
        parts.append(response.reply)
    if not parts:
        parts.append("Não encontrei nenhum gasto com valor na sua mensagem. Pode me dizer quanto foi?")

    return {
        "extracted_items": response.items,
        "final_response": "\n\n".join(parts)
    }

def node_query(state: AssistantState):
    response = run_query(state["user_message"])
    return {"query_tool_calls": response.tool_calls}

def node_db_execute(state: AssistantState):
    db_results = [_run_query_tool(call, state["user_id"]) for call in state["query_tool_calls"]]
    return {"db_results": db_results}

def node_secretary(state: AssistantState):
    query_results = json.dumps(state["db_results"], ensure_ascii=False)
    response = run_secretary(state["user_message"], query_results)
    return {"final_response": response.reply}

def node_off_topic(state: AssistantState):
    return {"final_response": "Desculpe, só consigo te ajudar com suas finanças."}
