import copy
from typing import get_args

from schemas.agents_schemas import CategoryType

RECORD_EXPENSES = "record_expenses"

RECORDER_TOOLS = {
    "function_declarations": [
        {
            "name": RECORD_EXPENSES,
            "description": "Registers one or more expenses for the user. Call it once with every expense found in the message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "One entry per expense mentioned in the message.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "amount": {
                                    "type": "number",
                                    "description": 'Amount spent, in the currency of the family, using a dot for decimals ("12,50" -> 12.5).',
                                },
                                "category": {
                                    "type": "string",
                                    "enum": list(get_args(CategoryType)),
                                    "description": "Closest category for the expense.",
                                },
                                "description": {
                                    "type": "string",
                                    "description": 'Short description in the language of the user\'s message, taken from the user\'s words (e.g. "Pastel", "Uber para o trabalho").',
                                },
                                "date": {
                                    "type": "string",
                                    "description": "Date of the expense as YYYY-MM-DD. Omit when the user does not mention a date.",
                                },
                            },
                            "required": ["amount", "category", "description"],
                        },
                    },
                },
                "required": ["items"],
            },
        }
    ]
}


MERCHANT_PROPERTY = {
    "type": "string",
    "description": 'The place or company the money went to, only when the user names one (e.g. "Uber", "iFood", "Netflix"). Omit it otherwise.',
}


def recorder_tools(merchants_enabled: bool = False) -> dict:
    """The tool the recorder is given. The merchant is only offered while the family has merchants on."""
    if not merchants_enabled:
        return RECORDER_TOOLS
    tools = copy.deepcopy(RECORDER_TOOLS)
    tools["function_declarations"][0]["parameters"]["properties"]["items"]["items"]["properties"]["merchant"] = (
        MERCHANT_PROPERTY
    )
    return tools
