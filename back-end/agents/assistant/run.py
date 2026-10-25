import os
import sys
# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from google.genai import types
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from agents.common import today_context
from agents.assistant.prompt import ASSISTANT_SYSTEM_PROMPT
from agents.assistant.tools import ASSISTANT_TOOLS

MODEL = "gemini-3.5-flash"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def run_assistant(messages: list[types.Content], user_name: str) -> types.Content:
    """One model turn over the conversation so far. Returns the model's message (text and/or tool calls)."""
    config = types.GenerateContentConfig(
        system_instruction=ASSISTANT_SYSTEM_PROMPT.format(user_name=user_name, **today_context()),
        tools=[ASSISTANT_TOOLS],
        # The graph executes the tools itself so the user_id is always injected by our code
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.0,
    )

    response = client.models.generate_content(model=MODEL, contents=messages, config=config)

    # Keep the model's content as-is: it carries the thought signatures the next turn needs
    if response.candidates and response.candidates[0].content:
        return response.candidates[0].content
    return types.Content(role="model", parts=[])
