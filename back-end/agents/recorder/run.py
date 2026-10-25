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
from agents.recorder.tools import RECORDER_TOOLS, RECORD_EXPENSES
from schemas.agents_schemas import RecorderResponse, RecordExpensesArgs

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def run_recorder(user_input: str) -> RecorderResponse:
    model = genai.GenerativeModel("gemini-3.5-flash", tools=[RECORDER_TOOLS])

    generation_config = genai.GenerationConfig(temperature=0.0)

    # AUTO lets the model answer with text instead of calling the tool (e.g. to ask for a missing amount)
    tool_config = {"function_calling_config": {"mode": "AUTO"}}

    full_prompt = RECORDER_SYSTEM_PROMPT.format(user_message=user_input, **today_context())

    response = model.generate_content(
        full_prompt,
        generation_config=generation_config,
        tool_config=tool_config
    )

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
        return RecorderResponse(items=[], reply="Não consegui registrar esse gasto. Pode mandar de novo, com o valor e o que foi?")
