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

from agents.orchestrator.prompt import ORCHESTRATOR_SYSTEM_PROMPT
from schemas.agents_schemas import OrchestratorResponse


genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def run_orchestrator(user_input: str) -> OrchestratorResponse:
    model = genai.GenerativeModel("gemini-3.5-flash")
    
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=OrchestratorResponse,
        temperature=0.0 
    )
    
    full_prompt = f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\nUser input:\n{user_input}"
    
    response = model.generate_content(
        full_prompt,
        generation_config=generation_config
    )
    
    try:
        data = json.loads(response.text)
        return OrchestratorResponse(**data)
    except Exception:
        return OrchestratorResponse(message=user_input, type="off-topic")


print(run_orchestrator("16 mercado"))