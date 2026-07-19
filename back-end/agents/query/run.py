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

from agents.query.prompt import QUERY_SYSTEM_PROMPT
from schemas.agents_schemas import QueryResponse

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def run_query(user_question: str) -> QueryResponse:
    model = genai.GenerativeModel("gemini-3.5-flash")
    
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=QueryResponse,
        temperature=0.0 
    )
    
    full_prompt = QUERY_SYSTEM_PROMPT.format(user_question=user_question)
    
    response = model.generate_content(
        full_prompt,
        generation_config=generation_config
    )
    
    try:
        data = json.loads(response.text)
        return QueryResponse(**data)
    except Exception as e:
        print("ERROR PARSING JSON OR VALIDATING:", e)
        print("RAW RESPONSE TEXT:", response.text)
        return QueryResponse(sql_query="")


print(run_query("Quanto eu gastei com comida esse mês?"))
