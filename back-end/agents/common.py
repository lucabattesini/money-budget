from collections.abc import Mapping, Sequence
from datetime import date
from schemas.agents_schemas import ToolCall

WEEKDAY_NAMES = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def today_context() -> dict:
    """Today's date and weekday, for prompts that need to resolve relative dates."""
    today = date.today()
    return {"today": today.isoformat(), "weekday": WEEKDAY_NAMES[today.weekday()]}


def _to_python(value):
    """Recursively turn the SDK's proto map/list wrappers (proto-plus or raw protobuf) into dicts and lists."""
    if isinstance(value, Mapping):
        return {key: _to_python(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_to_python(item) for item in value]
    return value


def extract_tool_calls(response) -> tuple[list[ToolCall], str | None]:
    """Split a Gemini response into its function calls and any plain text it also returned."""
    tool_calls = []
    texts = []

    for candidate in response.candidates[:1]:
        for part in candidate.content.parts:
            if part.function_call and part.function_call.name:
                args = _to_python(part.function_call.args) if part.function_call.args else {}
                tool_calls.append(ToolCall(name=part.function_call.name, args=args))
            elif part.text:
                texts.append(part.text)

    text = "\n".join(texts).strip() or None
    return tool_calls, text
