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
from agents.recorder.prompt import RECORDER_SYSTEM_PROMPT
from agents.recorder.tools import RECORD_EXPENSES, RECORDER_TOOLS
from config import GEMINI_MODEL
from schemas.agents_schemas import RecorderResponse, RecordExpensesArgs
from schemas.family_settings import LANGUAGE_NAMES

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


# What is said when the model's answer cannot be used, in each language
CANNOT_RECORD = {
    "pt": "Não consegui registrar esse gasto. Pode mandar de novo, com o valor e o que foi?",
    "en": "I couldn't record that expense. Could you send it again, with the amount and what it was?",
}


# How a number typed by the user is read, in each language (the format follows the family's language)
NUMBER_RULES = {
    "pt": 'Brazilian decimals use a comma, so "12,50" is 12.5 and "1.200" is 1200.',
    "en": 'Decimals use a dot and thousands a comma, so "12.50" is 12.5 and "1,200" is 1200.',
}


def run_recorder(user_input: str, language: str = "pt") -> RecorderResponse:
    model = genai.GenerativeModel(GEMINI_MODEL, tools=[RECORDER_TOOLS])

    generation_config = genai.GenerationConfig(temperature=0.0)

    # AUTO lets the model answer with text instead of calling the tool (e.g. to ask for a missing amount)
    tool_config = {"function_calling_config": {"mode": "AUTO"}}

    full_prompt = RECORDER_SYSTEM_PROMPT.format(
        user_message=user_input,
        language_name=LANGUAGE_NAMES[language],
        number_rule=NUMBER_RULES[language],
        **today_context(),
    )

    response = model.generate_content(full_prompt, generation_config=generation_config, tool_config=tool_config)

    try:
        tool_calls, text = extract_tool_calls(response)
        items = []
        for call in tool_calls:
            if call.name == RECORD_EXPENSES:
                items.extend(RecordExpensesArgs(**call.args).items)
        return RecorderResponse(items=items, reply=text)
    except Exception as e:
        print("ERROR PARSING TOOL CALL OR VALIDATING:", e)
        print("RAW RESPONSE:", response)
        return RecorderResponse(items=[], reply=CANNOT_RECORD[language])
