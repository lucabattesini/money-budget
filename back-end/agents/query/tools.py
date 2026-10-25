from typing import get_args
from schemas.agents_schemas import CategoryType

LIST_TRANSACTIONS = "list_transactions"
SUMMARIZE_TRANSACTIONS = "summarize_transactions"

CATEGORY_NAMES = list(get_args(CategoryType))

# Filters shared by both tools; mirrors schemas.agents_schemas.QueryFiltersArgs
FILTER_PROPERTIES = {
    "start_date": {
        "type": "string",
        "description": "First day of the period (inclusive), YYYY-MM-DD.",
    },
    "end_date": {
        "type": "string",
        "description": "Last day of the period (inclusive), YYYY-MM-DD.",
    },
    "categories": {
        "type": "array",
        "items": {"type": "string", "enum": CATEGORY_NAMES},
        "description": "Only include these categories.",
    },
    "exclude_categories": {
        "type": "array",
        "items": {"type": "string", "enum": CATEGORY_NAMES},
        "description": "Leave these categories out.",
    },
    "search": {
        "type": "string",
        "description": "Text to look for in the transaction description (case-insensitive), e.g. \"uber\".",
    },
    "min_amount": {
        "type": "number",
        "description": "Minimum amount in reais (inclusive).",
    },
    "max_amount": {
        "type": "number",
        "description": "Maximum amount in reais (inclusive).",
    },
    "weekdays": {
        "type": "array",
        "items": {"type": "integer"},
        "description": "Days of the week to include: 0 = Sunday, 1 = Monday ... 6 = Saturday.",
    },
}

QUERY_TOOLS = {
    "function_declarations": [
        {
            "name": LIST_TRANSACTIONS,
            "description": "Returns individual transactions (description, amount, date, category). Use it to show, find or rank specific expenses.",
            "parameters": {
                "type": "object",
                "properties": {
                    **FILTER_PROPERTIES,
                    "order_by": {
                        "type": "string",
                        "enum": ["date", "amount"],
                        "description": "Sort field. Use \"amount\" for the biggest/smallest expenses. Default: date.",
                    },
                    "order_dir": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort direction. Default: desc.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of transactions (1-200). Default: 20.",
                    },
                },
            },
        },
        {
            "name": SUMMARIZE_TRANSACTIONS,
            "description": "Returns totals (sum, count, average and maximum) of the matching expenses, either overall or grouped. Use it for \"how much\" questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    **FILTER_PROPERTIES,
                    "group_by": {
                        "type": "string",
                        "enum": ["category", "day", "month", "year", "weekday"],
                        "description": "Split the totals by this dimension. Omit for a single overall total.",
                    },
                },
            },
        },
    ]
}
