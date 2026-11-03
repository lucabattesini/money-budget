"""What the assistant itself says (not the model), in each language a family can choose."""

MESSAGES: dict[str, dict[str, str]] = {
    "pt": {
        "registered": "Registrado!",
        "in_category": "em",
        "no_amount": "Não encontrei nenhum gasto com valor na sua mensagem. Pode me dizer quanto foi?",
        "off_topic": "Desculpe, só consigo te ajudar com suas finanças.",
    },
    "en": {
        "registered": "Recorded!",
        "in_category": "in",
        "no_amount": "I couldn't find any expense with an amount in your message. How much was it?",
        "off_topic": "Sorry, I can only help you with your finances.",
    },
}

# Same order as SQL's day-of-week: 0 = Sunday
WEEKDAY_NAMES = {
    "pt": ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"],
    "en": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
}
