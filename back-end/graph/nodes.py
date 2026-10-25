from datetime import datetime, date
from google.genai import types
from pydantic import ValidationError
from graph.state import AssistantState
from agents.assistant.run import run_assistant
from agents.assistant.tools import RECORD_EXPENSES, LIST_TRANSACTIONS, SUMMARIZE_TRANSACTIONS
from api.repositories.transactions_repo import create_transaction, list_transactions, aggregate_transactions
from api.repositories.categories_repo import get_category_by_name
from schemas.tables_schemas import Transaction, TransactionFilters
from schemas.agents_schemas import RecordExpensesArgs, QueryFiltersArgs, ListTransactionsArgs, SummarizeTransactionsArgs

# Same order as SQL's day-of-week: 0 = Sunday
SQL_WEEKDAY_NAMES = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"]

FALLBACK_RESPONSE = "Desculpe, não consegui concluir seu pedido. Pode tentar de novo?"

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

def _record_expenses(args: RecordExpensesArgs, user_id: int) -> dict:
    now = datetime.now()
    registered = []

    for item in args.items:
        cat_obj = get_category_by_name(item.category) or get_category_by_name("Outros")
        # Keep the current time so same-day ordering still makes sense; never store future dates
        expense_date = item.date if item.date and item.date <= date.today() else now.date()

        create_transaction(
            Transaction(
                label=item.description,
                value=round(item.amount * 100),
                category_id=cat_obj.id,
                date=datetime.combine(expense_date, now.time()),
            ),
            user_id,
        )
        registered.append({
            "description": item.description,
            "amount": item.amount,
            "category": cat_obj.name,
            "date": expense_date.isoformat(),
        })

    return {"registered": registered}

def _list_transactions(args: ListTransactionsArgs, user_id: int) -> dict:
    rows = list_transactions(
        user_id,
        _to_filters(args),
        order_by="value" if args.order_by == "amount" else "date",
        order_dir=args.order_dir,
        limit=args.limit,
    )
    return {
        "expenses": [
            {
                "description": t.label,
                "amount": t.value / 100,
                "date": t.date.date().isoformat() if t.date else None,
                "category": t.category_name,
            }
            for t in rows
        ]
    }

def _summarize_transactions(args: SummarizeTransactionsArgs, user_id: int) -> dict:
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
    return {"summary": result}

# Tool name -> (args schema, executor). Every executor receives the user_id from our code, never from the model.
TOOLS = {
    RECORD_EXPENSES: (RecordExpensesArgs, _record_expenses),
    LIST_TRANSACTIONS: (ListTransactionsArgs, _list_transactions),
    SUMMARIZE_TRANSACTIONS: (SummarizeTransactionsArgs, _summarize_transactions),
}

def _run_tool(call: types.FunctionCall, user_id: int) -> dict:
    if call.name not in TOOLS:
        return {"error": f"Unknown tool: {call.name}"}

    args_schema, executor = TOOLS[call.name]
    try:
        args = args_schema(**(call.args or {}))
    except ValidationError as e:
        # Sent back to the model so it can fix the arguments
        return {"error": f"Invalid arguments: {e.errors(include_url=False, include_context=False)}"}

    try:
        return executor(args, user_id)
    except ValueError as e:
        return {"error": str(e)}

def node_agent(state: AssistantState):
    message = run_assistant(state["messages"], state["user_name"])
    update = {"messages": state["messages"] + [message], "steps": state.get("steps", 0) + 1}

    if not any(part.function_call for part in message.parts or []):
        text = "".join(part.text for part in message.parts or [] if part.text and not part.thought).strip()
        update["final_response"] = text or FALLBACK_RESPONSE

    return update

def node_tools(state: AssistantState):
    last_message = state["messages"][-1]
    responses = []

    for part in last_message.parts or []:
        if not part.function_call:
            continue
        call = part.function_call
        result = _run_tool(call, state["user_id"])
        if "error" in result:
            print("TOOL ERROR:", call.name, call.args, result["error"])
        responses.append(types.Part(function_response=types.FunctionResponse(id=call.id, name=call.name, response=result)))

    return {"messages": state["messages"] + [types.Content(role="user", parts=responses)]}

def node_give_up(state: AssistantState):
    return {"final_response": FALLBACK_RESPONSE}
