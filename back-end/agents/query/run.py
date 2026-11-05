import os
import sys

# pyrefly: ignore [missing-import]
import google.generativeai as genai

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from agents.common import extract_tool_calls, today_context
from agents.query.prompt import QUERY_SYSTEM_PROMPT
from agents.query.tools import query_tools
from config import GEMINI_MODEL
from schemas.agents_schemas import QueryResponse
from schemas.family_settings import DEFAULT_TIMEZONE

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


MERCHANT_RULE = (
    "8. Merchants: the family records the place or company of its transactions. Use `merchants` to filter by one "
    '(e.g. "gastos no iFood") and `group_by` "merchant" for totals per merchant ("quanto gastei em cada lugar").\n'
)


def run_query(user_question: str, timezone: str = DEFAULT_TIMEZONE, merchants_enabled: bool = False) -> QueryResponse:
    model = genai.GenerativeModel(GEMINI_MODEL, tools=[query_tools(merchants_enabled)])

    generation_config = genai.GenerationConfig(temperature=0.0)

    # ANY forces at least one tool call: this agent only fetches data, it never replies
    tool_config = {"function_calling_config": {"mode": "ANY"}}

    full_prompt = QUERY_SYSTEM_PROMPT.format(
        user_question=user_question, merchant_rule=MERCHANT_RULE if merchants_enabled else "", **today_context(timezone)
    )

    response = model.generate_content(full_prompt, generation_config=generation_config, tool_config=tool_config)

    try:
        tool_calls, _ = extract_tool_calls(response)
        return QueryResponse(tool_calls=tool_calls)
    except Exception as e:
        print("ERROR PARSING TOOL CALLS:", e)
        print("RAW RESPONSE:", response)
        return QueryResponse(tool_calls=[])
