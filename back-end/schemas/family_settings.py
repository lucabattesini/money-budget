"""What a family can choose for how amounts and dates look and which language the assistant writes in.

The currency is only how an amount is shown and how the assistant speaks about it: amounts are always stored as integer
cents and never converted between currencies. The language is also the language of the number and date formats.
"""

from typing import Literal

Currency = Literal["BRL", "USD", "CAD", "EUR", "GBP"]
Language = Literal["pt", "en"]

# The symbol of each currency, and the name of each language as the assistant's prompts say it
CURRENCY_SYMBOLS: dict[str, str] = {"BRL": "R$", "USD": "US$", "CAD": "CA$", "EUR": "€", "GBP": "£"}
CURRENCY_NAMES: dict[str, str] = {
    "BRL": "reais",
    "USD": "US dollars",
    "CAD": "Canadian dollars",
    "EUR": "euros",
    "GBP": "pounds sterling",
}
LANGUAGE_NAMES: dict[str, str] = {"pt": "Portuguese (pt-BR)", "en": "English"}

DEFAULT_CURRENCY = "BRL"
DEFAULT_LANGUAGE = "pt"
