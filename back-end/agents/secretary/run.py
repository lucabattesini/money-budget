import os
import sys
import json
# pyrefly: ignore [missing-import]
import google.generativeai as genai
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from agents.secretary.prompt import SECRETARY_SYSTEM_PROMPT
from schemas.agents_schemas import SecretaryResponse

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def run_secretary(user_message: str, query_results: str) -> SecretaryResponse:
    model = genai.GenerativeModel("gemini-3.5-flash")
    
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=SecretaryResponse,
        temperature=0.0 
    )
    
    full_prompt = SECRETARY_SYSTEM_PROMPT.format(
        user_message=user_message,
        query_results=query_results
    )
    
    response = model.generate_content(
        full_prompt,
        generation_config=generation_config
    )
    
    try:
        data = json.loads(response.text)
        return SecretaryResponse(**data)
    except Exception as e:
        print("ERROR PARSING JSON OR VALIDATING:", e)
        print("RAW RESPONSE TEXT:", response.text)
        return SecretaryResponse(reply="Desculpe, ocorreu um erro ao processar sua resposta.")

print(run_secretary("Quais foram os meus 3 maiores gastos dessa semana e qual o total deles?", "[{'label': 'Supermercado Extra', 'value': 450, 'date': '2026-07-15'}, {'label': 'Posto Ipiranga', 'value': 210, 'date': '2026-07-16'}, {'label': 'Farmácia Pague Menos', 'value': 120, 'date': '2026-07-17'}, {'total_semana': 780}]"))