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
                                    "description": "Amount spent in reais, using a dot for decimals (\"12,50\" -> 12.5).",
                                },
                                "category": {
                                    "type": "string",
                                    "enum": list(get_args(CategoryType)),
                                    "description": "Closest category for the expense.",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Short description in Portuguese, taken from the user's words (e.g. \"Pastel\", \"Uber para o trabalho\").",
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
