import json
import os
import sys

# pyrefly: ignore [missing-import]
import google.generativeai as genai

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from agents.secretary.prompt import SECRETARY_SYSTEM_PROMPT
from config import GEMINI_MODEL
from schemas.agents_schemas import SecretaryResponse
from schemas.family_settings import CURRENCY_NAMES, CURRENCY_SYMBOLS, LANGUAGE_NAMES

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


# What is said when the model's answer cannot be used, in each language
CANNOT_ANSWER = {
    "pt": "Desculpe, ocorreu um erro ao processar sua resposta.",
    "en": "Sorry, something went wrong while preparing your answer.",
}


def run_secretary(
    user_message: str, query_results: str, currency: str = "BRL", language: str = "pt"
) -> SecretaryResponse:
    model = genai.GenerativeModel(GEMINI_MODEL)

    generation_config = genai.GenerationConfig(
        response_mime_type="application/json", response_schema=SecretaryResponse, temperature=0.0
    )

    full_prompt = SECRETARY_SYSTEM_PROMPT.format(
        user_message=user_message,
        query_results=query_results,
        language_name=LANGUAGE_NAMES[language],
        currency_name=CURRENCY_NAMES[currency],
        currency_symbol=CURRENCY_SYMBOLS[currency],
    )

    response = model.generate_content(full_prompt, generation_config=generation_config)

    try:
        data = json.loads(response.text)
        return SecretaryResponse(**data)
    except Exception as e:
        print("ERROR PARSING JSON OR VALIDATING:", e)
        print("RAW RESPONSE TEXT:", response.text)
        return SecretaryResponse(reply=CANNOT_ANSWER[language])
