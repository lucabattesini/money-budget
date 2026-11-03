import json
from datetime import date, datetime

from pydantic import ValidationError
from sqlalchemy.orm import Session

from agents.orchestrator.run import run_orchestrator
from agents.query.run import run_query
from agents.query.tools import LIST_TRANSACTIONS, SUMMARIZE_TRANSACTIONS
from agents.recorder.run import run_recorder
from agents.secretary.run import run_secretary
from api.repositories.categories_repo import get_category_by_name
from api.repositories.families_repo import get_family
from api.repositories.transactions_repo import aggregate_transactions, create_transaction, list_transactions
from api.utils.formatting import format_day_month, format_money
from db.connection import session_scope
from graph.messages import MESSAGES, WEEKDAY_NAMES
from graph.state import AssistantState
from schemas.agents_schemas import ListTransactionsArgs, QueryFiltersArgs, SummarizeTransactionsArgs, ToolCall
from schemas.tables_schemas import Transaction, TransactionFilters


def _to_cents(amount: float | None) -> int | None:
    return None if amount is None else round(amount * 100)


def _category_ids(db: Session, family_id: int, names: list[str] | None) -> list[int] | None:
    if not names:
        return None
    # An unknown name maps to -1 so it matches nothing instead of silently widening the filter
    return [cat.id if (cat := get_category_by_name(db, name, family_id)) else -1 for name in names]


def _to_filters(db: Session, family_id: int, args: QueryFiltersArgs) -> TransactionFilters:
    return TransactionFilters(
        start_date=args.start_date,
        end_date=args.end_date,
        category_ids=_category_ids(db, family_id, args.categories),
        exclude_category_ids=_category_ids(db, family_id, args.exclude_categories),
        search=args.search,
        min_value=_to_cents(args.min_amount),
        max_value=_to_cents(args.max_amount),
        weekdays=args.weekdays,
    )


def _run_query_tool(db: Session, call: ToolCall, family_id: int, language: str = "pt") -> dict:
    """Execute one query tool call for the family and return its result with amounts in the family's currency
    (whole units, not cents)."""
    try:
        if call.name == LIST_TRANSACTIONS:
            args = ListTransactionsArgs(**call.args)
            rows = list_transactions(
                db,
                family_id,
                _to_filters(db, family_id, args),
                order_by="value" if args.order_by == "amount" else "date",
                order_dir=args.order_dir,
                limit=args.limit,
            )
            result = [
                {
                    "description": t.label,
                    "amount": t.value / 100,
                    "date": t.transactioned_at.date().isoformat() if t.transactioned_at else None,
                    "category": t.category_name,
                }
                for t in rows
            ]
        elif call.name == SUMMARIZE_TRANSACTIONS:
            args = SummarizeTransactionsArgs(**call.args)
            rows = aggregate_transactions(db, family_id, _to_filters(db, family_id, args), args.group_by)
            result = []
            for row in rows:
                item = {}
                if args.group_by == "category":
                    item["category"] = row.category_name
                elif args.group_by == "weekday":
                    item["weekday"] = WEEKDAY_NAMES[language][row.weekday]
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
    with session_scope() as db:
        family = get_family(db, state["family_id"])
        currency, language = family.currency, family.language
    response = run_recorder(state["user_message"], language=language)
    text = MESSAGES[language]
    now = datetime.now()

    registered = []
    with session_scope() as db:
        for item in response.items:
            cat_obj = get_category_by_name(db, item.category, state["family_id"]) or get_category_by_name(
                db, "Sem categoria", state["family_id"]
            )
            # Keep the current time so same-day ordering still makes sense; never store future dates
            expense_date = item.date if item.date and item.date <= date.today() else now.date()

            t = Transaction(
                label=item.description,
                value=round(item.amount * 100),
                category_id=cat_obj.id,
                transactioned_at=datetime.combine(expense_date, now.time()),
            )
            create_transaction(db, t, state["family_id"], state["user_id"])
            registered.append(
                f"• {format_money(item.amount, currency, language)} {text['in_category']} {cat_obj.name} "
                f"({item.description}, {format_day_month(expense_date, language)})"
            )

    parts = []
    if registered:
        parts.append(text["registered"] + "\n" + "\n".join(registered))
    if response.reply:
        parts.append(response.reply)
    if not parts:
        parts.append(text["no_amount"])

    return {"extracted_items": response.items, "final_response": "\n\n".join(parts)}


def node_query(state: AssistantState):
    response = run_query(state["user_message"])
    return {"query_tool_calls": response.tool_calls}


def node_db_execute(state: AssistantState):
    with session_scope() as db:
        language = get_family(db, state["family_id"]).language
        db_results = [_run_query_tool(db, call, state["family_id"], language) for call in state["query_tool_calls"]]
    return {"db_results": db_results}


def node_secretary(state: AssistantState):
    query_results = json.dumps(state["db_results"], ensure_ascii=False)
    with session_scope() as db:
        family = get_family(db, state["family_id"])
        currency, language = family.currency, family.language
    response = run_secretary(state["user_message"], query_results, currency=currency, language=language)
    return {"final_response": response.reply}


def node_off_topic(state: AssistantState):
    with session_scope() as db:
        language = get_family(db, state["family_id"]).language
    return {"final_response": MESSAGES[language]["off_topic"]}
