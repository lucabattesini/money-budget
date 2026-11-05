"""What a family can choose for how amounts and dates look, which language the assistant writes in and where it lives.

The currency is only how an amount is shown and how the assistant speaks about it: amounts are always stored as integer
cents and never converted between currencies. The language is also the language of the number and date formats.
The timezone says which clock "now" is read from: a transaction's date and time are the wall-clock time of the family
(TKT-65), so a purchase made at 22:30 on the last day of the month stays in that month wherever the server runs.
"""

from typing import Literal

Currency = Literal["BRL", "USD", "CAD", "EUR", "GBP"]
Language = Literal["pt", "en"]
Timezone = Literal[
    "America/Sao_Paulo",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Toronto",
    "America/Vancouver",
    "Europe/Lisbon",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "UTC",
]

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
DEFAULT_TIMEZONE = "America/Sao_Paulo"
