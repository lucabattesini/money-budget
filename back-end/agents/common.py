from datetime import date

WEEKDAY_NAMES = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def today_context() -> dict:
    """Today's date and weekday, for prompts that need to resolve relative dates."""
    today = date.today()
    return {"today": today.isoformat(), "weekday": WEEKDAY_NAMES[today.weekday()]}
